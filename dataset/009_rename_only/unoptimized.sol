// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Adder {
    function compute(uint256 alpha, uint256 beta) external pure returns (uint256) {
        uint256 gamma = alpha + beta;
        return gamma;
    }
}
