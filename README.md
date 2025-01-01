# avax-cross-verify

A utility to copy a contract verification to/from snowtrace.io/snowscan.xyz

I have repeatedly had issues where a contract is verified on only one of these explorers. Trivial changes to your forge
project can make it annoying to verify a contract after deployment. I created this tool to simplify the process of
ensuring that it's verified on both of them, if it's verified on one of them.

```
cd python
pip install -r requirements.txt
python cross_verify.py <0xaddress>
```

## Limitations

Currently this only works on contracts verified using `solidity-standard-json-input`, but that includes all the
commonly used dev tools like Foundry and Hardhat. Remix might do single file upload, not sure.

I think it also doesn't support contracts using `library` but I didn't have any at hand to test with.

Open to PRs if you want to fix anything.
