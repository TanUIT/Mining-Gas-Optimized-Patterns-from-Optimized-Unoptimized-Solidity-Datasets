// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Config {
    uint256 public fee;

    constructor(uint256 f) {
        fee = f;
    }

    function quote(uint256 x) external view returns (uint256) {
        return x * fee;
    }
}
