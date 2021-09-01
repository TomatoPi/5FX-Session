cmake_minimum_required(VERSION 3.13.0)
project(5FX-Patcher VERSION 0.1.0)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(HEADERS )
set(SOURCES nsm-jack-patch.cpp)

link_libraries(NSMWrap)
link_libraries(sfx)
link_libraries(lo)

add_executable(${PROJECT_NAME} ${SOURCES})
# add_executable(5FX-Server nsm-server.py)

install(TARGETS ${PROJECT_NAME})