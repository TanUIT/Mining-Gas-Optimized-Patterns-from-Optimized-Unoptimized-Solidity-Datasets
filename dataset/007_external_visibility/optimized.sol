// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Api {
    function ping(uint256 x) external pure returns (uint256) {
        return x + 1;
    }
}
