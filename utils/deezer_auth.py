import sys
import deezer
from utils.logger import setup_logger

def get_authenticated_client(config, logger):
    """
    Set up the Deezer Client using the ARL cookie from the configuration.
    """
    arl = config.get('config', {}).get('arl_token')
    user_id = config.get('config', {}).get('user_id')

    # Check if the ARL token is present and valid.
    if not arl or arl == "PASTE_YOUR_ARL_HERE":
        logger.error("ARL token is missing in config.yml")
        sys.exit(1)

    # Prepare headers for the Deezer API request using the ARL cookie.
    headers = {
        "Cookie": f"arl={arl}",
        "Accept-Language": "en-US",
    }

    # Get batch size from config or default to 50
    batch_size = config.get('config', {}).get('batch_size', 50)

    try:
        client = deezer.Client(headers=headers)
        
        # Attach the batch size to the client for global access
        client.batch_size = batch_size

        # Test connection using the numeric user_id
        if user_id:
            user = client.get_user(user_id)
            logger.info(f"Authenticated successfully as: {user.name}")
        else:
            # Fallback test if user_id isn't provided (checking a public track)
            client.get_track(3135556)
            logger.warning("Connection successful, but user_id is missing in config.yml. "
                           "Exclusion strategies may fail without it.")
        
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Deezer API: {e}")
        logger.debug("Check if your ARL token has expired or if your user_id is correct.")
        sys.exit(1)