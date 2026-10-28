cmake_minimum_required(VERSION 3.10)
project(CppVPN)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED True)

# Find Boost libraries (Asio, System)
find_package(Boost REQUIRED COMPONENTS asio system)

# Add executable
add_executable(vpn_server main.cpp)

# Link libraries
target_link_libraries(vpn_server PRIVATE Boost::asio Boost::system)