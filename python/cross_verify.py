import json
import os
import re
import sys
import time

import requests

# I don't think the snowtrace API key actually matters.
SNOWTRACE_API_KEY = os.getenv('SNOWTRACE_API_KEY', default='C586QJU38EB7IYM79XTGRDV46BM2E2V82N')

# Here's a default key I created not like I'm paying anything for it.
SNOWSCAN_API_KEY = os.getenv('SNOWSCAN_API_KEY', default='C586QJU38EB7IYM79XTGRDV46BM2E2V82N')

SNOWTRACE_API = 'https://api.snowtrace.io/api'
SNOWSCAN_API = 'https://api.snowscan.xyz/api'


def check_verification(url: str, contract_address: str, api_key: str) -> bool:
    params = {
        'module': 'contract',
        'action': 'getsourcecode',
        'address': contract_address,
        'apikey': api_key,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()

    if data['status'] == '0':
        return False

    if not isinstance(data, dict) or 'status' not in data or 'result' not in data:
        raise ValueError(f"Invalid API response format: {data}")

    if not isinstance(data['result'], list) or not data['result']:
        raise ValueError(f"No result data returned: {data}")

    result = data['result'][0]
    if not isinstance(result, dict) or 'SourceCode' not in result:
        raise ValueError(f"Invalid result format: {result}")

    return bool(result['SourceCode'])


def fetch_contract(url: str, contract_address: str, api_key: str):
    params = {
        'module': 'contract',
        'action': 'getsourcecode',
        'address': contract_address,
        'apikey': api_key,
    }

    response = requests.get(url, params=params)
    data = response.json()

    if data['status'] == '1' and data['message'] == 'OK':
        return data['result'][0]
    else:
        raise Exception(f'Error fetching contract: {data["message"]}')


def fetch_contract_from_snowscan(contract_address):
    url = 'https://api.snowscan.xyz/api'
    params = {
        'module': 'contract',
        'action': 'getsourcecode',
        'address': contract_address,
        'apikey': SNOWSCAN_API_KEY
    }

    response = requests.get(url, params=params)
    if response.status_code == 200:
        data = response.json()
        if data['status'] == '1' and data['message'] == 'OK':
            return data['result'][0]
    raise Exception(f'Error fetching contract: {response.status_code}')


def verify_contract(contract_data: dict, contract_address: str, url: str, api_key: str):
    source_code = contract_data['SourceCode'].strip()
    # No idea why it returns this invalid json, but we have to clean it up first.
    if source_code.startswith('{{') and source_code.endswith('}}'):
        source_code = source_code[1:-1]

    # Need to identify the file with the contract in it. Very half-ass implementation though.
    contract_name = contract_data['ContractName']
    source_code_data = json.loads(source_code)
    contract_file = None
    for file_name, file_data in source_code_data['sources'].items():
        if f'contract {contract_name}'.lower() in file_data['content'].lower():
            contract_file = file_name
            break

    # Only support json input for now, which is what forge uses. Feel free to PR for the other types.
    code_format = 'solidity-standard-json-input'

    # This is only required for snowscan? But works fine for both.
    constructor_args = contract_data.get('ConstructorArguments', '')
    if constructor_args.startswith('0x'):
        constructor_args = constructor_args[2:]

    form_data = {
        'apikey': api_key,
        'module': 'contract',
        'action': 'verifysourcecode',
        'contractaddress': contract_address,
        'sourceCode': source_code,
        'codeformat': code_format,
        'contractname': f'{contract_file}:{contract_name}',
        'compilerversion': (contract_data['CompilerVersion']),
        'optimizationUsed': int(contract_data['OptimizationUsed']),
        'runs': int(contract_data.get('Runs', 200)),
        'constructorArguments': constructor_args,
        'evmversion': contract_data.get('EVMVersion', 'default').lower(),
        'licenseType': (contract_data.get('LicenseType', '') or '3'),
    }

    response = requests.post(url, data=form_data)

    result = response.json()
    if result['status'] == '1':
        return result.get('result')
    else:
        raise Exception(f'Verification failed\n\nFull error response: {json.dumps(result, indent=2)}')


def check_verification_status(url: str, guid: str, api_key: str):
    params = {
        'module': 'contract',
        'action': 'checkverifystatus',
        'guid': guid,
        'apikey': api_key,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    result = response.json()
    return result.get('result')


def main():
    if len(sys.argv) != 2:
        print('Usage: python script.py <contract_address>')
        sys.exit(1)

    contract_address = sys.argv[1]
    if not re.match(r'^0x[a-fA-F0-9]{40}$', contract_address):
        print('Invalid contract address')
        sys.exit(1)

    print('Checking verification status')
    status_snowtrace = check_verification(SNOWTRACE_API, contract_address, SNOWTRACE_API_KEY)
    status_snowscan = check_verification(SNOWSCAN_API, contract_address, SNOWSCAN_API_KEY)

    if status_snowtrace and status_snowscan:
        print('Contract is already verified on both platforms.')
        exit(0)
    elif not status_snowtrace and not status_snowscan:
        print('Contract is not verified on either platform.')
        exit(1)

    from_api_url = SNOWTRACE_API if status_snowtrace else SNOWSCAN_API
    from_api_key = SNOWTRACE_API_KEY if status_snowtrace else SNOWSCAN_API_KEY
    to_api_url = SNOWSCAN_API if status_snowtrace else SNOWTRACE_API
    to_api_key = SNOWSCAN_API_KEY if status_snowtrace else SNOWTRACE_API_KEY

    print(f'Fetching from {from_api_url} and verifying on {to_api_url}')
    contract_data = fetch_contract(from_api_url, contract_address, from_api_key)

    print(f'Verifying {contract_address}')
    guid = verify_contract(contract_data, contract_address, to_api_url, to_api_key)

    print(f'Checking verification status for {guid}')
    while True:
        status = check_verification_status(to_api_url, guid, to_api_key)
        print(f'Current status: {status}')

        if any([x in status.lower() for x in ['pass', 'fail', 'verified', 'rejected', 'error']]):
            break

        time.sleep(5)

    print(f'Final verification status: {status}')


if __name__ == '__main__':
    main()
