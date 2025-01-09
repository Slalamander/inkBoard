"Types for inkBoard"

from typing import TypedDict

class inkboardrequirements(TypedDict):
    "Dict for indicating inkBoard related requirements for platform.json or manifest.json"

    inkboard_version: str
    "The inkBoard version requirement. Can use a comparison if needed."

    pssm_version: str
    "Required Python Screen Stack Manager version"

    platforms: list[str]
    "List of required platforms. Requires at least one of the list entries for the requirement to be met."

    integrations: list[str]
    "List of required integrations. All integrations must be installed for the requirement to be met."


class platformjson(TypedDict):
    """Base dict that should be gathered from a platform.json file

    Used to indicate the platforms version, requirements and the like.
    """

    version: str
    "Version string. Use x.x.x for versioning"

    requirements: list[str]
    "List with requirements. Follows conventions for pip install"

    optional_requirements: dict[str,list[str]]
    "Optional requirements that can be installed for i.e. implementing more features"

    inkboard_requirements: inkboardrequirements
    "inkBoard specific requirements"

    description: str
    "Optional description of the platform"

    ##Also include: maintainer etc. similar to manifest json

class manifestjson(TypedDict):
    "Dict for inidicating requirements for integrations"
    
    version: str
    "Version string. Use x.x.x for versioning"

    requirements: list[str]
    "List with requirements. Follows conventions for pip install"

    optional_requirements: dict[str,list[str]]
    "Optional requirements that can be installed for i.e. implementing more features"

    inkboard_requirements: inkboardrequirements
    "inkBoard specific requirements"