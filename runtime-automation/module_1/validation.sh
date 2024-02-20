#!/bin/bash

# Function to generate a random number between 1 and 10
generate_random_number() {
  echo $(( ( RANDOM % 10 )  + 1 ))
}

# Main script
random_number=$(generate_random_number)

# Check if the random number is less than or equal to 5
if [ $random_number -le 5 ]; then
  echo "Random number is $random_number. Script failed."
  exit 1
else
  echo "Random number is $random_number. Script succeeded."
  exit 0
fi