![inkBoard Logo](https://raw.githubusercontent.com/Slalamander/inkBoard/78ff69ea4cb7540b49c96f563f95c5c5224af16e/assets/blue_logo_vector.svg)

inkBoard is a dashboarding software that uses the [PythonScreenStackManager](https://github.com/Slalamander/PythonScreenStackManager) library to make it possible to use the dashboards on any platforms that support it. There is also a designer package, which is a tool to allow designing dashboards on desktop without the limitations of whatever platform it is meant to be deployed to, as well as giving a gui to certain actions easier.

The system is designed with extendability in mind, such that new platforms can easily be implemented, and to allow integrations to implement new features, elements, and the like. The idea is that by making it easy to write integrations and implement them, inkBoard can be used for various simple dashboards.  

## Install
`pip install inkBoard`

# Documentation

WIP

# Examples

See the example folder for a small configuration file to make a dashboard. It can be run by using the command `inkBoard run configuration.yaml` from the folder. Keep in mind it won't run without having the desktop platform installed.
