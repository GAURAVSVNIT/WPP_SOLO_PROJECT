from .models import SpotifyToken
from django.utils import timezone
from datetime import timedelta
from .credentials import CLIENT_ID, CLIENT_SECRET
from requests import post, put, get, ConnectionError, Timeout, RequestException
import time
import logging

# Set up logging
logger = logging.getLogger(__name__)


BASE_URL = "https://api.spotify.com/v1/me/"


def get_user_tokens(session_id):
    user_tokens = SpotifyToken.objects.filter(user=session_id)

    if user_tokens.exists():
        return user_tokens[0]
    else:
        return None


def update_or_create_user_tokens(session_id, access_token, token_type, expires_in, refresh_token):
    tokens = get_user_tokens(session_id)
    expires_in = timezone.now() + timedelta(seconds=expires_in)

    if tokens:
        tokens.access_token = access_token
        tokens.refresh_token = refresh_token
        tokens.expires_in = expires_in
        tokens.token_type = token_type
        tokens.save(update_fields=['access_token',
                                   'refresh_token', 'expires_in', 'token_type'])
    else:
        tokens = SpotifyToken(user=session_id, access_token=access_token,
                              refresh_token=refresh_token, token_type=token_type, expires_in=expires_in)
        tokens.save()


def is_spotify_authenticated(session_id):
    tokens = get_user_tokens(session_id)
    if tokens:
        expiry = tokens.expires_in
        if expiry <= timezone.now():
            refresh_spotify_token(session_id)

        return True

    return False


def clear_spotify_tokens(session_id):
    """Clear invalid Spotify tokens from the database."""
    tokens = get_user_tokens(session_id)
    if tokens:
        logger.warning(f"Clearing invalid Spotify tokens for session {session_id}")
        tokens.delete()
    return True

def refresh_spotify_token(session_id):
    tokens = get_user_tokens(session_id)
    if not tokens:
        logger.error(f"No tokens found for session {session_id}")
        return False
        
    refresh_token = tokens.refresh_token
    
    # Maximum retry attempts
    max_retries = 3
    retry_delay = 1  # seconds
    
    for attempt in range(max_retries):
        try:
            response = post(
                'https://accounts.spotify.com/api/token', 
                data={
                    'grant_type': 'refresh_token',
                    'refresh_token': refresh_token,
                    'client_id': CLIENT_ID,
                    'client_secret': CLIENT_SECRET
                },
                timeout=10  # Set a timeout
            )
            
            # Check if we got a 400 Bad Request error (invalid token)
            if response.status_code == 400:
                logger.error(f"Spotify token refresh failed with 400 Bad Request - invalid refresh token")
                # Clear the invalid tokens
                clear_spotify_tokens(session_id)
                return False
                
            # Check for other HTTP errors
            response.raise_for_status()
            
            response_data = response.json()
            
            # Check for error in response
            if 'error' in response_data:
                logger.error(f"Spotify API error: {response_data.get('error_description', 'Unknown error')}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                    continue
                
                # Check if it's an invalid token error
                error_desc = response_data.get('error_description', '').lower()
                if 'invalid' in error_desc and 'token' in error_desc:
                    clear_spotify_tokens(session_id)
                
                return False
                
            access_token = response_data.get('access_token')
            token_type = response_data.get('token_type')
            expires_in = response_data.get('expires_in')
            
            # If refresh token is returned, use it; otherwise, keep the old one
            new_refresh_token = response_data.get('refresh_token', refresh_token)
            
            update_or_create_user_tokens(
                session_id, access_token, token_type, expires_in, new_refresh_token)
            
            return True
            
        except ConnectionError as e:
            logger.error(f"Connection error when refreshing token: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            return False
            
        except Timeout as e:
            logger.error(f"Timeout when refreshing token: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            return False
            
        except RequestException as e:
            logger.error(f"Request exception when refreshing token: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            return False
            
        except Exception as e:
            logger.error(f"Unexpected error when refreshing token: {str(e)}")
            return False
    
    return False


def execute_spotify_api_request(session_id, endpoint, post_=False, put_=False, data=None):
    # Check if the user is authenticated and tokens are valid
    if not is_spotify_authenticated(session_id):
        logger.error(f"User {session_id} is not authenticated with Spotify")
        return {'error': 'Authentication error', 'message': 'User not authenticated with Spotify'}
    
    tokens = get_user_tokens(session_id)
    if not tokens:
        logger.error(f"No tokens found for session {session_id}")
        return {'error': 'Authentication error', 'message': 'No Spotify tokens found'}
    
    # Check token expiration and refresh if needed
    if tokens.expires_in <= timezone.now():
        logger.info(f"Token expired for session {session_id}, refreshing...")
        refresh_success = refresh_spotify_token(session_id)
        if not refresh_success:
            logger.error(f"Failed to refresh token for session {session_id}")
            return {'error': 'Authentication error', 'message': 'Failed to refresh Spotify token'}
        # Get updated tokens
        tokens = get_user_tokens(session_id)
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f"Bearer {tokens.access_token}"
    }
    
    url = BASE_URL + endpoint
    max_retries = 2
    retry_delay = 1  # seconds
    
    # Handle POST request
    if post_:
        for attempt in range(max_retries + 1):
            try:
                post_response = post(url, headers=headers, json=data, timeout=10)
                post_response.raise_for_status()
                break
            except (ConnectionError, Timeout) as e:
                logger.error(f"Connection error on POST to {endpoint}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {'error': 'Connection error', 'message': f'Failed to connect to Spotify API: {str(e)}'}
            except RequestException as e:
                status_code = getattr(e.response, 'status_code', None)
                if status_code == 401:  # Unauthorized, try to refresh token
                    refresh_success = refresh_spotify_token(session_id)
                    if refresh_success and attempt < max_retries:
                        tokens = get_user_tokens(session_id)
                        headers['Authorization'] = f"Bearer {tokens.access_token}"
                        time.sleep(0.5)
                        continue
                logger.error(f"Request error on POST to {endpoint}: {str(e)}")
                return {'error': 'API error', 'message': f'Spotify API error: {str(e)}'}
    
    # Handle PUT request
    if put_:
        for attempt in range(max_retries + 1):
            try:
                put_response = put(url, headers=headers, json=data, timeout=10)
                put_response.raise_for_status()
                break
            except (ConnectionError, Timeout) as e:
                logger.error(f"Connection error on PUT to {endpoint}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    return {'error': 'Connection error', 'message': f'Failed to connect to Spotify API: {str(e)}'}
            except RequestException as e:
                status_code = getattr(e.response, 'status_code', None)
                if status_code == 401:  # Unauthorized, try to refresh token
                    refresh_success = refresh_spotify_token(session_id)
                    if refresh_success and attempt < max_retries:
                        tokens = get_user_tokens(session_id)
                        headers['Authorization'] = f"Bearer {tokens.access_token}"
                        time.sleep(0.5)
                        continue
                logger.error(f"Request error on PUT to {endpoint}: {str(e)}")
                return {'error': 'API error', 'message': f'Spotify API error: {str(e)}'}
    
    # Handle GET request
    for attempt in range(max_retries + 1):
        try:
            get_response = get(url, {}, headers=headers, timeout=10)
            get_response.raise_for_status()
            
            return get_response.json()
            
        except (ConnectionError, Timeout) as e:
            logger.error(f"Connection error on GET to {endpoint}: {str(e)}")
            if attempt < max_retries:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return {'error': 'Connection error', 'message': f'Failed to connect to Spotify API: {str(e)}'}
        except RequestException as e:
            status_code = getattr(e.response, 'status_code', None)
            if status_code == 401:  # Unauthorized, try to refresh token
                refresh_success = refresh_spotify_token(session_id)
                if refresh_success and attempt < max_retries:
                    tokens = get_user_tokens(session_id)
                    headers['Authorization'] = f"Bearer {tokens.access_token}"
                    time.sleep(0.5)
                    continue
            logger.error(f"Request error on GET to {endpoint}: {str(e)}")
            return {'error': 'API error', 'message': f'Spotify API error: {str(e)}'}
        except ValueError as e:
            logger.error(f"JSON decode error for {endpoint}: {str(e)}")
            return {'error': 'Parse error', 'message': 'Invalid response from Spotify API'}
        except Exception as e:
            logger.error(f"Unexpected error for {endpoint}: {str(e)}")
            return {'error': 'Unknown error', 'message': f'An unexpected error occurred: {str(e)}'}
    
    return {'error': 'Request failed', 'message': 'All request attempts failed'}
def check_for_active_spotify_device(session_id, max_retries=2):
    """
    Check if there's an active Spotify device and try to activate one if not.
    Returns a tuple (success, message, device_name)
    """
    # Maximum retry attempts for getting devices
    for attempt in range(max_retries):
        # Get available devices
        devices = get_available_devices(session_id)
        
        if devices is None:
            if attempt < max_retries - 1:
                logger.warning(f"Failed to get devices, retrying in 1 second (attempt {attempt+1}/{max_retries})")
                time.sleep(1)
                continue
            return False, "Failed to retrieve Spotify devices", None
        
        # Check for active devices
        active_devices = [d for d in devices if d.get('is_active', True)]
        if active_devices:
            logger.info(f"Found active Spotify device: {active_devices[0].get('name', 'Unknown')}")
            return True, "Active device found", active_devices[0].get('name', 'Unknown')
        
        # If no active devices but there are available devices
        available_devices = devices
        if available_devices:
            # Try to activate the first available device
            logger.info(f"No active device found. Attempting to activate device: {available_devices[0].get('name', 'Unknown')}")
            
            # Try to transfer playback
            for transfer_attempt in range(2):
                transfer_result = execute_spotify_api_request(
                    session_id, 
                    "player", 
                    put_=True, 
                    data={
                        "device_ids": [available_devices[0].get('id')],
                        "play": False  # Don't auto-play yet
                    }
                )
                
                if transfer_result is None or 'error' not in transfer_result:
                    logger.info(f"Successfully activated device: {available_devices[0].get('name', 'Unknown')}")
                    return True, f"Activated Spotify on {available_devices[0].get('name', 'Unknown')}", available_devices[0].get('name', 'Unknown')
                
                # If failed to transfer, try again after a short delay
                error_msg = transfer_result.get('message', 'Unknown error')
                logger.warning(f"Failed to activate device (attempt {transfer_attempt+1}/2): {error_msg}")
                
                if transfer_attempt < 1:
                    time.sleep(1)
        
        # If we got here with no success and there are retries left
        if attempt < max_retries - 1:
            logger.warning(f"No active Spotify devices found, retrying in 2 seconds (attempt {attempt+1}/{max_retries})")
            time.sleep(2)
    
    # If we exhausted all retries, check if there were any devices at all
    devices = get_available_devices(session_id)
    if not devices or len(devices) == 0:
        return False, "No Spotify devices found. Please open Spotify on any device and try again.", None
    
    return False, "Failed to activate Spotify device. Please manually start playback on your device.", None

def get_available_devices(session_id):
    """
    Get a list of available Spotify devices for the user.
    """
    result = execute_spotify_api_request(session_id, "player/devices")
    if result and 'error' in result:
        logger.error(f"Error getting devices for session {session_id}: {result.get('message', 'Unknown error')}")
        return None
        
    return result.get('devices', [])

def play_song(session_id):
    """
    Start or resume playback on user's Spotify account.
    Checks for active devices and handles common errors.
    Returns dict with error information if unsuccessful.
    """
    # First check if we have an active Spotify device
    success, message, device_name = check_for_active_spotify_device(session_id)
    
    if not success:
        # If we couldn't find or activate a device, return a helpful error
        logger.error(f"Cannot play song: {message}")
        raise ConnectionError(message)
    
    # Log the action
    logger.info(f"Attempting to play song on device: {device_name}")
    
    # Try to play
    result = execute_spotify_api_request(session_id, "player/play", put_=True)
    
    # Handle specific error cases
    if result and 'error' in result:
        error_message = result.get('message', 'Unknown error')
        
        # Extract Spotify error code if present
        if 'Spotify API error:' in error_message and '403' in error_message:
            error_message = "Cannot control playback: No active device found or premium required. Please start Spotify on a device first."
        elif 'Spotify API error:' in error_message and '404' in error_message:
            error_message = "No active Spotify device found. Please open Spotify on your device."
        elif 'Spotify API error:' in error_message and '401' in error_message:
            error_message = "Authentication error. Please reconnect your Spotify account."
        
        logger.error(f"Error playing song for session {session_id}: {error_message}")
        raise ConnectionError(error_message)
        
    return result

def pause_song(session_id):
    """
    Pause playback on user's Spotify account.
    Returns dict with error information if unsuccessful.
    """
    # First check if we have an active Spotify device
    success, message, device_name = check_for_active_spotify_device(session_id)
    
    if not success:
        # If we couldn't find or activate a device, return a helpful error
        logger.error(f"Cannot pause song: {message}")
        raise ConnectionError(message)
    
    # Log the action
    logger.info(f"Attempting to pause song on device: {device_name}")
    
    # Try to pause
    result = execute_spotify_api_request(session_id, "player/pause", put_=True)
    
    # Handle errors
    if result and 'error' in result:
        error_message = result.get('message', 'Unknown error')
        
        # Extract Spotify error code if present
        if 'Spotify API error:' in error_message and '403' in error_message:
            error_message = "Cannot control playback: No active device found or premium required."
        elif 'Spotify API error:' in error_message and '404' in error_message:
            error_message = "No active Spotify device found. Please open Spotify on your device."
        
        logger.error(f"Error pausing song for session {session_id}: {error_message}")
        raise ConnectionError(error_message)
        
    return result


def skip_song(session_id):
    """
    Skip to the next track in user's Spotify queue.
    Returns dict with error information if unsuccessful.
    """
    # First check if we have an active Spotify device
    success, message, device_name = check_for_active_spotify_device(session_id)
    
    if not success:
        # If we couldn't find or activate a device, return a helpful error
        logger.error(f"Cannot skip song: {message}")
        raise ConnectionError(message)
    
    # Log the action
    logger.info(f"Attempting to skip song on device: {device_name}")
    
    # Try to skip
    result = execute_spotify_api_request(session_id, "player/next", post_=True)
    
    # Handle errors
    if result and 'error' in result:
        error_message = result.get('message', 'Unknown error')
        
        # Extract Spotify error code if present
        if 'Spotify API error:' in error_message and '403' in error_message:
            error_message = "Cannot control playback: No active device found or premium required."
        elif 'Spotify API error:' in error_message and '404' in error_message:
            error_message = "No active Spotify device found. Please open Spotify on your device."
        
        logger.error(f"Error skipping song for session {session_id}: {error_message}")
        raise ConnectionError(error_message)
        
    return result
