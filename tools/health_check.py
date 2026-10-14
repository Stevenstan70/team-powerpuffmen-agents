from ibm_watsonx_orchestrate.agent_builder.tools import tool, ToolPermission


@tool(permission=ToolPermission.READ_ONLY)
def health_check(message: str) -> dict:
    """Smoke-test tool that echoes a message with a fixed 'ok' status.

    Args:
        message (str): An arbitrary string to echo back in the response.

    Returns:
        dict: A dictionary containing 'status' set to 'ok' and 'message'
              set to the supplied string.
    """
    return {"status": "ok", "message": message}
