// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Guard {
    error NotOwner();

    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function protected() external view returns (uint256) {
        if (msg.sender != owner) revert NotOwner();
        return 42;
    }
}
