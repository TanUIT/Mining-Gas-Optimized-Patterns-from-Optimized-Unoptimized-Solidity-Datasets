// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract Vault {
    mapping(address => uint256) public balance;

    function deposit() external payable {
        balance[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(
            balance[msg.sender] >= amount,
            "Vault: insufficient balance to complete this withdrawal request"
        );
        balance[msg.sender] -= amount;
    }
}
