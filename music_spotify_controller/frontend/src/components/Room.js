import React, { Component } from "react";
import { 
  Grid, 
  Button, 
  Typography, 
  Card, 
  CardContent, 
  Box, 
  IconButton, 
  LinearProgress, 
  Tooltip, 
  Chip,
  Container,
  Fade,
  CircularProgress,
  Divider,
  Badge,
  Slider,
  Paper,
  Snackbar,
  Link
} from "@material-ui/core";
import { Alert, AlertTitle } from "@material-ui/lab";
import PlayArrowIcon from "@material-ui/icons/PlayArrow";
import PauseIcon from "@material-ui/icons/Pause";
import SkipNextIcon from "@material-ui/icons/SkipNext";
import SettingsIcon from "@material-ui/icons/Settings";
import VolumeUpIcon from "@material-ui/icons/VolumeUp";
import VolumeDownIcon from "@material-ui/icons/VolumeDown";
import MeetingRoomIcon from "@material-ui/icons/MeetingRoom";
import GroupIcon from "@material-ui/icons/Group";
import CheckCircleIcon from "@material-ui/icons/CheckCircle";
import ErrorIcon from "@material-ui/icons/Error";
import MusicNoteIcon from "@material-ui/icons/MusicNote";
import LockIcon from "@material-ui/icons/Lock";
import HelpOutlineIcon from "@material-ui/icons/HelpOutline";
import CreateRoomPage from "./CreateRoomPage";

// Premium feature notice component
const PremiumFeatureNotice = ({ open, onClose }) => (
  <Snackbar 
    open={open} 
    autoHideDuration={10000} 
    onClose={onClose}
    anchorOrigin={{ vertical: 'top', horizontal: 'center' }}
  >
    <Alert 
      severity="info" 
      variant="filled"
      onClose={onClose}
      style={{ maxWidth: '600px' }}
    >
      <AlertTitle>Spotify Premium Required</AlertTitle>
      <p>
        Playback controls like play, pause, and skip require a Spotify Premium account.
      </p>
      <Box mt={1}>
        <Link 
          href="https://www.spotify.com/premium/" 
          target="_blank" 
          rel="noopener"
          style={{ color: 'white', textDecoration: 'underline' }}
        >
          Learn more about Spotify Premium
        </Link>
      </Box>
    </Alert>
  </Snackbar>
);

export default class Room extends Component {
  constructor(props) {
    super(props);
    this.state = {
      votesToSkip: 2,
      guestCanPause: false,
      isHost: false,
      showSettings: false,
      spotifyAuthenticated: false,
      song: {},
      loading: true,
      volume: 50,
      actionLoading: {
        play: false,
        pause: false,
        skip: false,
        leave: false
      },
      notification: {
        show: false,
        message: "",
        type: "info" // info, success, error, warning
      },
      spotifyError: null,
      showPremiumNotice: false,
    };
    this.roomCode = this.props.match.params.roomCode;
    this.leaveButtonPressed = this.leaveButtonPressed.bind(this);
    this.updateShowSettings = this.updateShowSettings.bind(this);
    this.renderSettingsButton = this.renderSettingsButton.bind(this);
    this.renderSettings = this.renderSettings.bind(this);
    this.getRoomDetails = this.getRoomDetails.bind(this);
    this.getRoomDetails = this.getRoomDetails.bind(this);
    this.authenticateSpotify = this.authenticateSpotify.bind(this);
    this.getCurrentSong = this.getCurrentSong.bind(this);
    this.skipSong = this.skipSong.bind(this);
    this.pauseSong = this.pauseSong.bind(this);
    this.playSong = this.playSong.bind(this);
    this.formatTime = this.formatTime.bind(this);
    this.handleCloseNotification = this.handleCloseNotification.bind(this);
    this.handleApiError = this.handleApiError.bind(this);
    this.handlePremiumNoticeClose = this.handlePremiumNoticeClose.bind(this);
    this.getRoomDetails();
  }
  componentDidMount() {
    this.interval = setInterval(this.getCurrentSong, 1000);
  }

  componentWillUnmount() {
    clearInterval(this.interval);
  }

  getRoomDetails() {
    return fetch("/api/get-room" + "?code=" + this.roomCode)
      .then((response) => {
        if (!response.ok) {
          this.props.leaveRoomCallback();
          this.props.history.push("/");
        }
        return response.json();
      })
      .then((data) => {
        this.setState({
          votesToSkip: data.votes_to_skip,
          guestCanPause: data.guest_can_pause,
          isHost: data.is_host,
          loading: false
        });
        if (this.state.isHost) {
          this.authenticateSpotify();
        }
      })
      .catch(error => {
        console.error("Error fetching room details:", error);
        this.setState({ loading: false });
      });
  }

  authenticateSpotify() {
    fetch("/spotify/is-authenticated")
      .then((response) => response.json())
      .then((data) => {
        this.setState({ 
          spotifyAuthenticated: data.status,
          spotifyTokenInfo: data.token_info || {}
        });
        
        // If not authenticated or token is expired/invalid, get auth URL
        if (!data.status || (data.token_info && !data.token_info.has_valid_token)) {
          fetch("/spotify/get-auth-url")
            .then((response) => response.json())
            .then((data) => {
              window.location.replace(data.url);
            });
        }
      })
      .catch(error => {
        console.error("Error checking Spotify authentication:", error);
        this.showNotification("Spotify authentication error. Please try again.", "error");
      });
  }

  getCurrentSong() {
    fetch("/spotify/current-song")
      .then((response) => {
        // Check if we got a 401 Unauthorized (auth required)
        if (response.status === 401) {
          return response.json().then(data => {
            // Re-authenticate if auth URL is provided
            if (data.auth_url) {
              this.showNotification("Spotify authentication required. Redirecting...", "info");
              setTimeout(() => {
                window.location.replace(data.auth_url);
              }, 2000);
            } else {
              this.authenticateSpotify(); // Otherwise use the standard auth flow
            }
            throw new Error("Authentication required");
          });
        }
        
        if (!response.ok) {
          return {};
        } else {
          return response.json();
        }
      })
      .then((data) => {
        // Check if we need to reauthenticate
        if (data.requires_authentication) {
          this.showNotification("Spotify authentication required. Redirecting...", "info");
          setTimeout(() => {
            if (data.auth_url) {
              window.location.replace(data.auth_url);
            } else {
              this.authenticateSpotify();
            }
          }, 2000);
          return;
        }
        
        this.setState({ song: data });
      })
      .catch(error => {
        // Ignore auth errors as they're handled above
        if (error.message !== "Authentication required") {
          console.error("Error fetching current song:", error);
        }
      });
  }
  skipSong() {
    // Set loading state for skip action
    this.setState(prevState => ({
      actionLoading: {
        ...prevState.actionLoading,
        skip: true
      }
    }));

    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };

    fetch("/spotify/skip", requestOptions)
      .then(response => {
        if (response.ok) {
          this.showNotification("Skipped to next track", "success");
        } else {
          return response.json().then(data => {
            throw new Error(data.error || "Failed to skip track");
          });
        }
      })
      .catch(error => {
        this.handleApiError(error, "Failed to skip track");
      })
      .finally(() => {
        // Clear loading state
        setTimeout(() => {
          this.setState(prevState => ({
            actionLoading: {
              ...prevState.actionLoading,
              skip: false
            }
          }));
        }, 500);
      });
  }

  pauseSong() {
    // Set loading state for pause action
    this.setState(prevState => ({
      actionLoading: {
        ...prevState.actionLoading,
        pause: true
      }
    }));

    const requestOptions = {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    };

    fetch("/spotify/pause", requestOptions)
      .then(response => {
        if (response.ok) {
          this.showNotification("Playback paused", "info");
        } else {
          return response.json().then(data => {
            throw new Error(data.error || "Failed to pause playback");
          });
        }
      })
      .catch(error => {
        this.handleApiError(error, "Failed to pause playback");
      })
      .finally(() => {
        // Clear loading state
        setTimeout(() => {
          this.setState(prevState => ({
            actionLoading: {
              ...prevState.actionLoading,
              pause: false
            }
          }));
        }, 500);
      });
  }

  playSong() {
    // Set loading state for play action
    this.setState(prevState => ({
      actionLoading: {
        ...prevState.actionLoading,
        play: true
      }
    }));

    const requestOptions = {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    };

    fetch("/spotify/play", requestOptions)
      .then(response => {
        if (response.ok) {
          this.showNotification("Playback started", "success");
        } else {
          return response.json().then(data => {
            throw new Error(data.error || "Failed to start playback");
          });
        }
      })
      .catch(error => {
        this.handleApiError(error, "Failed to start playback");
      })
      .finally(() => {
        // Clear loading state
        setTimeout(() => {
          this.setState(prevState => ({
            actionLoading: {
              ...prevState.actionLoading,
              play: false
            }
          }));
        }, 500);
      });
  }

  handleVolumeChange(event, newValue) {
    this.setState({ volume: newValue });
    // Note: This would need a corresponding API endpoint to actually change Spotify volume
  }

  showNotification(message, type = "info") {
    this.setState({
      notification: {
        show: true,
        message,
        type
      }
    });
  }

  handleCloseNotification() {
    this.setState({
      notification: {
        ...this.state.notification,
        show: false
      }
    });
  }

  handleApiError(error, fallbackMessage) {
    console.error(error);
    
    // Check if this is a premium requirement error
    const errorMsg = error.message || fallbackMessage;
    const isPremiumError = errorMsg.includes('premium') || 
                          errorMsg.toLowerCase().includes('forbidden') || 
                          errorMsg.includes('403');
                          
    if (isPremiumError) {
      this.setState({
        showPremiumNotice: true,
        spotifyError: "Spotify Premium Required",
        notification: {
          show: true,
          message: "This feature requires Spotify Premium",
          type: "info"
        }
      });
    } else {
      this.setState({
        spotifyError: errorMsg,
        notification: {
          show: true,
          message: errorMsg,
          type: "error"
        }
      });
    }
  }
  
  handlePremiumNoticeClose() {
    this.setState({ showPremiumNotice: false });
  }
  leaveButtonPressed() {
    // Set loading state for leave action
    this.setState(prevState => ({
      actionLoading: {
        ...prevState.actionLoading,
        leave: true
      }
    }));

    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    };

    fetch("/api/leave-room", requestOptions)
      .then(response => {
        if (response.ok) {
          this.showNotification("Leaving room...", "info");
          setTimeout(() => {
            this.props.leaveRoomCallback();
            this.props.history.push("/");
          }, 1000);
        } else {
          throw new Error("Failed to leave room");
        }
      })
      .catch(error => {
        console.error("Error leaving room:", error);
        this.setState({
          notification: {
            show: true,
            message: "Error leaving room. Please try again.",
            type: "error"
          },
          actionLoading: {
            ...this.state.actionLoading,
            leave: false
          }
        });
      });
  }

  updateShowSettings(value) {
    this.setState({
      showSettings: value,
    });
  }

  formatTime(ms) {
    if (!ms) return "0:00";
    
    const minutes = Math.floor(ms / 60000);
    const seconds = ((ms % 60000) / 1000).toFixed(0);
    return `${minutes}:${seconds.padStart(2, '0')}`;
  }

  renderSettings() {
    return (
      <Container maxWidth="md">
        <Fade in={true} timeout={500}>
          <Card className="music-card">
            <CardContent>
              <Grid container spacing={3}>
                <Grid item xs={12} align="center">
                  <Typography variant="h4" className="main-title">
                    Room Settings
                  </Typography>
                </Grid>
                
                <Grid item xs={12} align="center">
                  <CreateRoomPage
                    update={true}
                    votesToSkip={this.state.votesToSkip}
                    guestCanPause={this.state.guestCanPause}
                    roomCode={this.roomCode}
                    updateCallback={this.getRoomDetails}
                  />
                </Grid>
                
                <Grid item xs={12} align="center">
                  <Button
                    className="action-button"
                    variant="contained"
                    onClick={() => this.updateShowSettings(false)}
                  >
                    Back to Music
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Fade>
      </Container>
    );
  }

  renderSettingsButton() {
    return (
      <Tooltip title="Room Settings">
        <IconButton 
          className="control-button"
          onClick={() => this.updateShowSettings(true)}
        >
          <SettingsIcon />
        </IconButton>
      </Tooltip>
    );
  }

  render() {
    if (this.state.loading) {
      return (
        <Box display="flex" flexDirection="column" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress className="loading-pulse" size={60} />
          <Typography variant="h6" className="loading-pulse" style={{ marginTop: 20 }}>
            Loading Room...
          </Typography>
        </Box>
      );
    }

    if (this.state.showSettings) {
      return this.renderSettings();
    }

    const { song, notification, actionLoading, showPremiumNotice } = this.state;
    const songProgress = (song.time / song.duration) * 100 || 0;
    const isPremiumFeature = true; // Assume all playback controls are premium features
    return (
      <Container maxWidth="md">
        <Fade in={true} timeout={500}>
          <div>
            {/* Room Information Card */}
            <Card className="music-card" elevation={3}>
              <CardContent>
                <Grid container spacing={2} alignItems="center">
                  <Grid item xs={12} sm={6} align="center">
                    <div className="room-code">
                      <Typography variant="h6" component="span">
                        Room Code: {this.roomCode}
                      </Typography>
                    </div>
                  </Grid>
                  <Grid item xs={12} sm={6} align="center">
                    <Chip 
                      icon={this.state.isHost ? <CheckCircleIcon /> : <GroupIcon />} 
                      label={this.state.isHost ? "Host" : "Guest"} 
                      color={this.state.isHost ? "primary" : "default"}
                      style={{ marginRight: 8 }}
                    />
                    <Chip 
                      icon={this.state.spotifyAuthenticated ? <CheckCircleIcon /> : <ErrorIcon />} 
                      label="Spotify" 
                      color={this.state.spotifyAuthenticated ? "primary" : "secondary"}
                    />
                  </Grid>
                </Grid>
              </CardContent>
            </Card>

            {/* Music Player Card */}
            <Card className="music-card" style={{ marginTop: 20 }}>
              <CardContent>
                {!song.title ? (
                  <Box display="flex" flexDirection="column" alignItems="center" p={3}>
                    <MusicNoteIcon style={{ fontSize: 60, color: "#1e3c72", marginBottom: 20 }} />
                    <Typography variant="h5" style={{ color: "#666" }}>
                      No song currently playing
                    </Typography>
                    <Typography variant="body2" style={{ color: "#888", marginTop: 10 }}>
                      Play a song on Spotify to get started
                    </Typography>
                  </Box>
                ) : (
                  <Grid container spacing={3}>
                    {/* Album Art */}
                    <Grid item xs={12} md={4} align="center">
                      <Box className="album-cover" mb={2}>
                        <img src={song.image_url} alt={song.title} style={{ width: '100%', height: 'auto' }} />
                      </Box>
                      
                      {/* Vote Information */}
                      {/* Vote Information */}
                      <Paper elevation={2} style={{ padding: '8px 15px', display: 'inline-block', borderRadius: '20px' }}>
                        <Typography variant="body2">
                          Votes to Skip: <b>{song.votes || 0}</b> / <b>{song.votes_required || this.state.votesToSkip}</b>
                        </Typography>
                      </Paper>
                    </Grid>
                    
                    {/* Song Info and Controls */}
                    <Grid item xs={12} md={8} className="song-info">
                      <Typography variant="h4" component="h2" gutterBottom>
                        {song.title}
                      </Typography>
                      <Typography variant="h6" color="textSecondary" gutterBottom>
                        {song.artist}
                      </Typography>
                      
                      {/* Progress Bar */}
                      <Box my={3}>
                        <Grid container spacing={2} alignItems="center">
                          <Grid item xs={2}>
                            <Typography variant="body2">{this.formatTime(song.time)}</Typography>
                          </Grid>
                          <Grid item xs={8}>
                            <LinearProgress 
                              variant="determinate" 
                              value={songProgress} 
                              className="progress-bar"
                            />
                          </Grid>
                          <Grid item xs={2} align="right">
                            <Typography variant="body2">{this.formatTime(song.duration)}</Typography>
                          </Grid>
                        </Grid>
                      </Box>
                      
                      {/* Music Controls */}
                      <Box className="music-controls" mb={3}>
                        {this.state.guestCanPause || this.state.isHost ? (
                          <Tooltip title={song.is_playing ? "Pause" : "Play"}>
                            <div>
                              <IconButton 
                                className={`control-button ${song.is_playing ? "pause-button" : "play-button"}`}
                                onClick={() => song.is_playing ? this.pauseSong() : this.playSong()}
                                size="medium"
                                disabled={actionLoading.play || actionLoading.pause}
                              >
                                {actionLoading.play || actionLoading.pause ? (
                                  <CircularProgress size={24} color="inherit" />
                                ) : song.is_playing ? (
                                  <PauseIcon fontSize="large" />
                                ) : (
                                  <PlayArrowIcon fontSize="large" />
                                )}
                              </IconButton>
                            </div>
                          </Tooltip>
                        ) : null}
                        <Tooltip title={
                          <div>
                            <Typography variant="body2">Skip</Typography>
                            <Typography variant="caption">Requires Spotify Premium</Typography>
                          </div>
                        }>
                          <div style={{ position: 'relative' }}>
                            <Badge badgeContent={`${song.votes}/${song.votes_required}`} color="secondary">
                              <IconButton 
                                className="control-button skip-button"
                                onClick={this.skipSong}
                                size="medium"
                                disabled={actionLoading.skip}
                              >
                                {actionLoading.skip ? (
                                  <CircularProgress size={24} color="inherit" />
                                ) : (
                                  <SkipNextIcon fontSize="large" />
                                )}
                                {isPremiumFeature && (
                                  <div style={{ 
                                    position: 'absolute', 
                                    top: -5, 
                                    right: -5, 
                                    background: 'rgba(0,0,0,0.5)', 
                                    borderRadius: '50%',
                                    padding: 3
                                  }}>
                                    <LockIcon style={{ fontSize: 12, color: '#1DB954' }} />
                                  </div>
                                )}
                              </IconButton>
                            </Badge>
                          </div>
                        </Tooltip>
                        
                        {this.state.isHost && this.renderSettingsButton()}
                      </Box>
                      
                      {/* Volume Control */}
                      <Box mx={2} mb={2}>
                        <Grid container spacing={2} alignItems="center">
                          <Grid item>
                            <VolumeDownIcon />
                          </Grid>
                          <Grid item xs>
                            <Slider
                              value={this.state.volume}
                              onChange={this.handleVolumeChange}
                              aria-labelledby="volume-slider"
                            />
                          </Grid>
                          <Grid item>
                            <VolumeUpIcon />
                          </Grid>
                        </Grid>
                      </Box>
                    </Grid>
                  </Grid>
                )}
              </CardContent>
            </Card>
            
            {/* Leave Room Button */}
            <Box mt={3} mb={5} display="flex" justifyContent="center">
              <Button
                className="action-button leave-button"
                variant="contained"
                size="large"
                startIcon={actionLoading.leave ? <CircularProgress size={24} color="inherit" /> : <MeetingRoomIcon />}
                onClick={this.leaveButtonPressed}
                disabled={actionLoading.leave}
              >
                {actionLoading.leave ? "Leaving..." : "Leave Room"}
              </Button>
            </Box>
            {/* Premium Notice */}
            {song.title && (
              <Card className="music-card" style={{ marginTop: 20 }}>
                <CardContent>
                  <Grid container spacing={2} alignItems="center">
                    <Grid item>
                      <HelpOutlineIcon style={{ color: '#1DB954' }} />
                    </Grid>
                    <Grid item xs>
                      <Typography variant="body1">
                        <strong>Note:</strong> Playback controls require Spotify Premium. 
                        The display will update as songs play, but you'll need a premium account to control playback.
                      </Typography>
                    </Grid>
                  </Grid>
                </CardContent>
              </Card>
            )}
          </div>
        </Fade>

        {/* Premium Feature Notice */}
        <PremiumFeatureNotice 
          open={showPremiumNotice} 
          onClose={this.handlePremiumNoticeClose} 
        />

        {/* Notification Snackbar */}
        <Snackbar
          open={notification.show}
          autoHideDuration={6000}
          onClose={this.handleCloseNotification}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          <Alert 
            onClose={this.handleCloseNotification} 
            severity={notification.type}
            variant="filled"
          >
            {notification.message}
          </Alert>
        </Snackbar>
      </Container>
    );
  }
}
