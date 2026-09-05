// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Guard {
    address public owner;

    constructor() {
        owner = msg.sender;
    }

    function protected() external view returns (uint256) {
        require(msg.sender == owner, "Guard: caller is not the authorized owner account");
        return 42;
    }
}
