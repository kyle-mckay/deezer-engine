import sys
import deezer
from utils.logger import setup_logger

def get_authenticated_client(config, logger):
    """
    Initialize a Deezer client using the ARL cookie from the config.
    """
    arl = config.get('config', {}).get('arl_token')
    user_id = config.get('config', {}).get('user_id')

    # Ensure an ARL token is provided in the configuration
    if not arl or arl == "PASTE_YOUR_ARL_HERE":
        logger.error("ARL token is missing in config.yml")
        sys.exit(1)

    # Build request headers with the ARL cookie
    headers = {
        "Cookie": f"arl={arl}",
        "Accept-Language": "en-US",
    }

    # Read batch size from config (default: 50)
    batch_size = config.get('config', {}).get('batch_size', 50)

    try:
        client = deezer.Client(headers=headers)
        
        # Store the batch size on the client for later use
        client.batch_size = batch_size

        # If a user_id is provided, use it to verify authentication
        if user_id:
            user = client.get_user(user_id)
            logger.info(f"Authenticated successfully as: {user.name}")
        else:
            # If no user_id, perform a simple public request as a sanity check
            client.get_track(3135556)
            logger.warning("Connection successful, but user_id is missing in config.yml. "
                           "Exclusion strategies may fail without it.")
        
        return client

    except Exception as e:
        logger.error(f"Failed to connect to Deezer API: {e}")
        logger.debug("Check if your ARL token has expired or if your user_id is correct.")
        sys.exit(1)