cmake_minimum_required(VERSION 3.16)

project(SentenceExtractor)

set(CMAKE_CXX_STANDARD 17)

find_package(Qt6 REQUIRED COMPONENTS Core)

qt_standard_project_setup()

add_executable(SentenceExtractor
    src/main.cpp
)

target_link_libraries(SentenceExtractor Qt6::Core)
