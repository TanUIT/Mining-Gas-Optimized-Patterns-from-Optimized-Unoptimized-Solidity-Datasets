// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Adder {
    function compute(uint256 a, uint256 b) external pure returns (uint256) {
        uint256 c = a + b;
        return c;
    }
}
