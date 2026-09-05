// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Packer {
    struct Point {
        uint256 x;
        uint256 y;
        uint256 z;
    }

    Point public p;

    function set(uint256 a, uint256 b, uint256 c) external {
        p = Point(a, b, c);
    }
}
