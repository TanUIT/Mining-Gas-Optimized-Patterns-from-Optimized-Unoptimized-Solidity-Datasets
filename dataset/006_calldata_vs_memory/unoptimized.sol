// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Hasher {
    function total(uint256[] memory xs) external pure returns (uint256 s) {
        for (uint256 i = 0; i < xs.length; i++) {
            s += xs[i];
        }
    }
}
