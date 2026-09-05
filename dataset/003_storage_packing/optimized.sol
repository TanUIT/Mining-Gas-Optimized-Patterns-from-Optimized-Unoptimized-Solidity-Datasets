// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Packer {
    struct Point {
        uint64 x;
        uint64 y;
        uint128 z;
    }

    Point public p;

    function set(uint64 a, uint64 b, uint128 c) external {
        p = Point(a, b, c);
    }
}
