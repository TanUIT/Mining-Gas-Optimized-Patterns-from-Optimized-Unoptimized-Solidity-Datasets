// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Averager {
    uint256[] public data;

    function seed(uint256 n) external {
        for (uint256 i = 0; i < n; i++) {
            data.push(i);
        }
    }

    function stats() external view returns (uint256 total, uint256 count) {
        uint256[] memory cached = data;
        uint256 len = cached.length;
        for (uint256 i = 0; i < len; i++) {
            total += cached[i];
        }
        count = len;
    }
}
