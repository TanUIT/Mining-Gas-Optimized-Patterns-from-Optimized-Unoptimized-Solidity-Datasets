// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Counter {
    function loop(uint256 n) external pure returns (uint256 s) {
        for (uint256 i = 0; i < n;) {
            s += i;
            unchecked {
                ++i;
            }
        }
    }
}
