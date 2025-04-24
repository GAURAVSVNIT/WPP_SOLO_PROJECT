from django.shortcuts import render, redirect
from .credentials import REDIRECT_URI, CLIENT_SECRET, CLIENT_ID, SCOPE
from rest_framework.views import APIView
from requests import Request, post, ConnectionError, Timeout, RequestException
from rest_framework.response import Response
from rest_framework import status
import logging

# Set up logger
logger = logging.getLogger('spotify.views')
from .util import *
from .util import check_for_active_spotify_device, get_available_devices
from api.models import Room
from .models import Vote


class AuthURL(APIView):
    def get(self, request, format=None):
        try:
            logger.info("Generating Spotify authorization URL")
            
            # Use the comprehensive scope from credentials
            url = Request('GET', 'https://accounts.spotify.com/authorize', params={
                'scope': SCOPE,
                'response_type': 'code',
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID
            }).prepare().url
            
            logger.debug(f"Generated auth URL with scopes: {SCOPE}")
            return Response({'url': url})
            
        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}")
            return Response(
                {'error': 'Failed to generate Spotify authorization URL', 'details': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


def spotify_callback(request, format=None):
    code = request.GET.get('code')
    error = request.GET.get('error')
    
    
    if error:
        logger.error(f"Spotify auth callback received error: {error}")
        return redirect('frontend:')
    
    if not code:
        logger.error("Spotify auth callback received no code parameter")
        return redirect('frontend:')
    
    logger.info(f"Exchanging auth code for token")
    
    try:
        response = post(
            'https://accounts.spotify.com/api/token', 
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET
            },
            timeout=10
        )
        
        # Check for HTTP errors
        response.raise_for_status()
        
        response_data = response.json()
        
        if 'error' in response_data:
            logger.error(f"Spotify token exchange error: {response_data.get('error_description', 'Unknown error')}")
            return redirect('frontend:')
            
        logger.info("Successfully obtained Spotify access token")
        
    except ConnectionError as e:
        # Log the connection error
        logger.error(f"Spotify connection error during token exchange: {str(e)}")
        return redirect('frontend:')
    except Timeout as e:
        # Log the timeout error
        logger.error(f"Timeout during Spotify token exchange: {str(e)}")
        return redirect('frontend:')
    except RequestException as e:
        # Log request exceptions
        logger.error(f"Request exception during Spotify token exchange: {str(e)}")
        return redirect('frontend:')
    except Exception as e:
        # Log any other errors
        logger.error(f"Unexpected error during Spotify authentication: {str(e)}")
        return redirect('frontend:')
        
    # Extract token data from response
    access_token = response_data.get('access_token')
    token_type = response_data.get('token_type')
    refresh_token = response_data.get('refresh_token')
    expires_in = response_data.get('expires_in')
    error = response_data.get('error')
    
    if error:
        logger.error(f"Error in Spotify token response: {error}")
        return redirect('frontend:')
        
    if not access_token or not refresh_token:
        logger.error("Missing access_token or refresh_token in Spotify response")
        return redirect('frontend:')

    if not request.session.exists(request.session.session_key):
        request.session.create()
        logger.debug(f"Created new session with key: {request.session.session_key}")
    else:
        logger.debug(f"Using existing session with key: {request.session.session_key}")

    logger.info(f"Storing Spotify tokens for user session")
    update_or_create_user_tokens(
        request.session.session_key, access_token, token_type, expires_in, refresh_token)

    return redirect('frontend:')


class IsAuthenticated(APIView):
    def get(self, request, format=None):
        session_key = self.request.session.session_key
        
        if not session_key:
            logger.warning("No session key found when checking authentication")
            return Response({'status': False, 'error': 'No session found'}, status=status.HTTP_400_BAD_REQUEST)
            
        try:
            is_authenticated = is_spotify_authenticated(session_key)
            logger.debug(f"Authentication status for session {session_key}: {is_authenticated}")
            
            # Get token information if authenticated
            token_info = {}
            if is_authenticated:
                token = get_user_tokens(session_key)
                if token:
                    token_info = {
                        'expires_in': (token.expires_in - timezone.now()).total_seconds() if token.expires_in > timezone.now() else 0,
                        'has_valid_token': token.expires_in > timezone.now()
                    }
            
            return Response({
                'status': is_authenticated,
                'token_info': token_info
            })
        except Exception as e:
            logger.error(f"Error checking authentication status: {str(e)}")
            return Response(
                {'status': False, 'error': 'Authentication check failed'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CurrentSong(APIView):
    def get(self, request, format=None):
        room_code = self.request.session.get('room_code')
        
        if not room_code:
            return Response({"error": "No room code in session"}, status=status.HTTP_404_NOT_FOUND)
            
        room = Room.objects.filter(code=room_code)
        if room.exists():
            room = room[0]
        else:
            return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
            
        host = room.host
        
        # Check if there's an active Spotify device
        devices = get_available_devices(host)
        has_devices = devices is not None and len(devices) > 0
        has_active_device = False
        
        if has_devices:
            active_devices = [d for d in devices if d.get('is_active', False)]
            has_active_device = len(active_devices) > 0
            if has_active_device:
                logger.info(f"Found active Spotify device: {active_devices[0].get('name', 'Unknown')}")
        device_info = {
            'has_devices': has_devices,
            'has_active_device': has_active_device,
            'devices': [{'id': d.get('id'), 'name': d.get('name'), 'type': d.get('type'), 'is_active': d.get('is_active', False)} 
                        for d in (devices or [])]
        }
        
        # Try to activate a device if host and no active device
        if request.session.session_key == host and has_devices and not has_active_device:
            logger.info("No active device found for host, attempting to activate one")
            success, message, device_name = check_for_active_spotify_device(host)
            if success:
                logger.info(f"Successfully activated device: {device_name}")
                device_info['has_active_device'] = True
                device_info['activated_device'] = device_name
        
        endpoint = "player/currently-playing"
        
        # Check for token refresh errors
        token = get_user_tokens(host)
        if not token:
            return Response({
                "error": "Authentication Required",
                "message": "Spotify authentication required. Please re-authenticate with Spotify.",
                "requires_authentication": True,
                "auth_url": Request('GET', 'https://accounts.spotify.com/authorize', params={
                    'scope': SCOPE,
                    'response_type': 'code',
                    'redirect_uri': REDIRECT_URI,
                    'client_id': CLIENT_ID
                }).prepare().url
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            response = execute_spotify_api_request(host, endpoint)
        except ConnectionError as e:
            error_msg = str(e)
            # Check if the error indicates an authentication issue
            if "authentication" in error_msg.lower() or "token" in error_msg.lower():
                # Clear invalid tokens
                clear_spotify_tokens(host)
                return Response({
                    "error": "Authentication Required",
                    "message": "Your Spotify session has expired. Please re-authenticate.",
                    "requires_authentication": True,
                    "auth_url": Request('GET', 'https://accounts.spotify.com/authorize', params={
                        'scope': SCOPE,
                        'response_type': 'code',
                        'redirect_uri': REDIRECT_URI,
                        'client_id': CLIENT_ID
                    }).prepare().url
                }, status=status.HTTP_401_UNAUTHORIZED)
            
            return Response({
                "error": "Failed to connect to Spotify API",
                "device_info": device_info,
                "requires_premium": True,
                "spotify_open": has_devices
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except Exception as e:
            error_msg = str(e)
            # Check if the error indicates an authentication issue
            if "authentication" in error_msg.lower() or "token" in error_msg.lower():
                # Clear invalid tokens
                clear_spotify_tokens(host)
                return Response({
                    "error": "Authentication Required",
                    "message": "Your Spotify session has expired. Please re-authenticate.",
                    "requires_authentication": True
                }, status=status.HTTP_401_UNAUTHORIZED)
                
            return Response({
                "error": str(e), 
                "device_info": device_info,
                "requires_premium": True,
                "spotify_open": has_devices
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Return device status even when no song is playing
        if 'error' in response or 'item' not in response:
            error_info = {}
            if 'error' in response:
                error_info = response.get('error', {})
                logger.warning(f"Spotify API error: {error_info}")
                
            status_msg = 'ready' if has_active_device else 'no_active_device'
            status_text = 'No song is currently playing'
            
            if not has_devices:
                status_msg = 'no_devices'
                status_text = 'No Spotify devices found. Please open Spotify on any device.'
            elif not has_active_device:
                status_text = 'No active Spotify device found. Please start Spotify on a device.'
                
            return Response({
                'is_playing': False,
                'device_info': device_info,
                'requires_premium': True,
                'spotify_open': has_devices,
                'message': status_text,
                'status': status_msg,
                'error_details': error_info,
                'has_premium': 'premium' not in str(error_info).lower()
            }, status=status.HTTP_200_OK)

        # Song is playing, extract details
        item = response.get('item')
        duration = item.get('duration_ms')
        progress = response.get('progress_ms')
        album_cover = item.get('album').get('images')[0].get('url')
        is_playing = response.get('is_playing')
        song_id = item.get('id')
        
        # Build artist string
        artist_string = ""
        for i, artist in enumerate(item.get('artists')):
            if i > 0:
                artist_string += ", "
            name = artist.get('name')
            artist_string += name

        votes = len(Vote.objects.filter(room=room, song_id=song_id))
        song = {
            'title': item.get('name'),
            'artist': artist_string,
            'duration': duration,
            'time': progress,
            'image_url': album_cover,
            'is_playing': is_playing,
            'votes': votes,
            'votes_required': room.votes_to_skip,
            'id': song_id,
            'device_info': device_info
        }
        self.update_room_song(room, song_id)
        
        return Response(song, status=status.HTTP_200_OK)
    def update_room_song(self, room, song_id):
        current_song = room.current_song

        if current_song != song_id:
            room.current_song = song_id
            room.save(update_fields=['current_song'])
            votes = Vote.objects.filter(room=room).delete()


class PauseSong(APIView):
    def put(self, request, format=None):
        room_code = self.request.session.get('room_code')
        if not room_code:
            return Response({"error": "Not in a room"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            room = Room.objects.filter(code=room_code)
            if not room.exists():
                return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
                
            room = room[0]
            if self.request.session.session_key == room.host or room.guest_can_pause:
                # Check for active Spotify device before attempting to pause
                success, message, device_name = check_for_active_spotify_device(room.host)
                
                if not success:
                    return Response({
                        "error": "No active Spotify device",
                        "message": message,
                        "details": "Please open Spotify on a device and try again."
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
                try:
                    pause_song(room.host)
                    return Response({}, status=status.HTTP_204_NO_CONTENT)
                except ConnectionError as e:
                    logger.error(f"Failed to pause playback: {str(e)}")
                    # Check for premium requirement error (403 Forbidden)
                    error_msg = str(e)
                    error_status = status.HTTP_503_SERVICE_UNAVAILABLE
                    error_response = {
                        "error": "Failed to connect to Spotify API",
                        "message": error_msg
                    }
                    
                    if "403" in error_msg:
                        error_response["error"] = "Spotify Premium Required"
                        error_response["message"] = "This action requires a Spotify Premium account"
                        error_response["details"] = "Playback control features like pause/play require Spotify Premium"
                    
                    return Response(error_response, status=error_status)
                except Exception as e:
                    logger.error(f"Error pausing song: {str(e)}")
                    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({"error": "You don't have permission to pause"}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PlaySong(APIView):
    def put(self, request, format=None):
        room_code = self.request.session.get('room_code')
        if not room_code:
            return Response({"error": "Not in a room"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            room = Room.objects.filter(code=room_code)
            if not room.exists():
                return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
                
            room = room[0]
            if self.request.session.session_key == room.host or room.guest_can_pause:
                # Check for active Spotify device before attempting to play
                success, message, device_name = check_for_active_spotify_device(room.host)
                
                if not success:
                    # Get available devices for better error message
                    devices = get_available_devices(room.host)
                    has_devices = devices is not None and len(devices) > 0
                    
                    error_message = message
                    if not has_devices:
                        error_message = "No Spotify devices found. Please open Spotify on any device and try again."
                    
                    return Response({
                        "error": "No active Spotify device",
                        "message": error_message,
                        "has_devices": has_devices,
                        "devices": [{'name': d.get('name'), 'type': d.get('type')} for d in (devices or [])]
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                
                logger.info(f"Attempting to play music on device: {device_name}")
                
                try:
                    play_song(room.host)
                    return Response({}, status=status.HTTP_204_NO_CONTENT)
                except ConnectionError as e:
                    # Check for premium requirement error (403 Forbidden)
                    error_msg = str(e)
                    logger.error(f"Failed to play music: {error_msg}")
                    
                    error_response = {
                        "error": "Failed to connect to Spotify API",
                        "message": error_msg,
                        "hint": "This may be due to Spotify premium requirements or device issues."
                    }
                    
                    if "403" in error_msg:
                        error_response["error"] = "Spotify Premium Required"
                        error_response["message"] = "This action requires a Spotify Premium account"
                        error_response["details"] = "Playback control features like pause/play require Spotify Premium"
                    elif "404" in error_msg:
                        error_response["error"] = "Player Not Available"
                        error_response["message"] = "No active player was found"
                        error_response["details"] = "Open Spotify on your device and start playing music first"
                    
                    return Response(error_response, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                except Exception as e:
                    logger.error(f"Error playing song: {str(e)}")
                    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                return Response({"error": "You don't have permission to play"}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SkipSong(APIView):
    def post(self, request, format=None):
        room_code = self.request.session.get('room_code')
        if not room_code:
            return Response({"error": "Not in a room"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            room = Room.objects.filter(code=room_code)
            if not room.exists():
                return Response({"error": "Room not found"}, status=status.HTTP_404_NOT_FOUND)
                
            room = room[0]
            votes = Vote.objects.filter(room=room, song_id=room.current_song)
            votes_needed = room.votes_to_skip

            if self.request.session.session_key == room.host or len(votes) + 1 >= votes_needed:
                votes.delete()
                
                # Check for active Spotify device before attempting to skip
                success, message, device_name = check_for_active_spotify_device(room.host)
                
                if not success:
                    return Response({
                        "error": "No active Spotify device",
                        "message": message,
                        "details": "Please open Spotify on a device and try again."
                    }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                    
                try:
                    logger.info(f"Attempting to skip song on device: {device_name}")
                    skip_song(room.host)
                except ConnectionError as e:
                    error_msg = str(e)
                    logger.error(f"Failed to skip song: {error_msg}")
                    
                    error_response = {
                        "error": "Failed to connect to Spotify API",
                        "message": error_msg
                    }
                    
                    if "403" in error_msg:
                        error_response["error"] = "Spotify Premium Required"
                        error_response["message"] = "Skipping tracks requires a Spotify Premium account"
                        error_response["details"] = "Playback control features require Spotify Premium"
                    elif "404" in error_msg:
                        error_response["error"] = "No Active Playback"
                        error_response["message"] = "Cannot find active playback to skip"
                        error_response["details"] = "Start playing music on Spotify first"
                    
                    return Response(error_response, status=status.HTTP_503_SERVICE_UNAVAILABLE)
                except Exception as e:
                    logger.error(f"Error skipping song: {str(e)}")
                    return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                # Create a new vote
                try:
                    vote = Vote(user=self.request.session.session_key,
                                room=room, song_id=room.current_song)
                    vote.save()
                except Exception as e:
                    return Response({"error": f"Failed to save vote: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            return Response({}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
