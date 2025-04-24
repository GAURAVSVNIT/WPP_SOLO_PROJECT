import React, { Component } from "react";
import { 
  TextField, 
  Button, 
  Grid, 
  Typography, 
  Box, 
  Card, 
  CardContent, 
  Fade, 
  CircularProgress,
  Snackbar,
  IconButton
} from "@material-ui/core";
import { Alert } from "@material-ui/lab";
import { Link, withRouter } from "react-router-dom";
import ArrowBackIcon from "@material-ui/icons/ArrowBack";
import MeetingRoomIcon from "@material-ui/icons/MeetingRoom";
import CheckCircleIcon from "@material-ui/icons/CheckCircle";
import CloseIcon from "@material-ui/icons/Close";

class RoomJoinPage extends Component {
  constructor(props) {
    super(props);
    this.state = {
      roomCode: "",
      error: "",
      isLoading: false,
      showSuccess: false,
      validCode: false,
    };
    this.handleTextFieldChange = this.handleTextFieldChange.bind(this);
    this.roomButtonPressed = this.roomButtonPressed.bind(this);
    this.handleCloseSnackbar = this.handleCloseSnackbar.bind(this);
    this.validateRoomCode = this.validateRoomCode.bind(this);
  }

  validateRoomCode(code) {
    // Room code should be alphanumeric and 6 characters
    return code.length >= 4 && code.length <= 8 && /^[A-Za-z0-9]+$/.test(code);
  }

  handleCloseSnackbar() {
    this.setState({ error: "", showSuccess: false });
  }

  render() {
    const { roomCode, error, isLoading, showSuccess, validCode } = this.state;
    
    return (
      <>
        <Fade in={true} timeout={800}>
          <Card className="music-card">
            <CardContent>
              <Grid container spacing={3}>
                <Grid item xs={12} align="center">
                  <Typography variant="h4" component="h1" className="main-title">
                    Join a Room
                  </Typography>
                </Grid>
                <Grid item xs={12} align="center">
                  <TextField
                    error={!!error}
                    label="Room Code"
                    placeholder="Enter a Room Code"
                    value={roomCode}
                    helperText={error || "Enter the 4-8 character room code"}
                    variant="outlined"
                    onChange={this.handleTextFieldChange}
                    fullWidth
                    disabled={isLoading}
                    style={{ maxWidth: '400px' }}
                    InputProps={{
                      style: { color: 'white' },
                      endAdornment: validCode && !error ? (
                        <CheckCircleIcon style={{ color: '#1DB954' }} />
                      ) : null,
                    }}
                    InputLabelProps={{
                      style: { color: 'rgba(255, 255, 255, 0.7)' }
                    }}
                  />
                </Grid>
                <Grid item xs={12} align="center">
                  <Button
                    className="action-button join-button"
                    variant="contained"
                    startIcon={isLoading ? <CircularProgress size={20} color="inherit" /> : <MeetingRoomIcon />}
                    onClick={this.roomButtonPressed}
                    size="large"
                    disabled={isLoading || !roomCode || !validCode}
                  >
                    {isLoading ? "Joining..." : "Enter Room"}
                  </Button>
                </Grid>
                <Grid item xs={12} align="center">
                  <Button 
                    className="action-button"
                    variant="outlined" 
                    startIcon={<ArrowBackIcon />}
                    component={Link}
                    to="/"
                    disabled={isLoading}
                    style={{ 
                      background: 'transparent', 
                      border: '1px solid rgba(255,255,255,0.2)',
                      opacity: isLoading ? 0.6 : 1
                    }}
                  >
                    Back
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Fade>

        {/* Error/Success Notification */}
        <Snackbar 
          open={!!error || showSuccess} 
          autoHideDuration={6000} 
          onClose={this.handleCloseSnackbar}
          anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
        >
          {error ? (
            <Alert 
              severity="error" 
              variant="filled"
              action={
                <IconButton size="small" color="inherit" onClick={this.handleCloseSnackbar}>
                  <CloseIcon fontSize="small" />
                </IconButton>
              }
            >
              {error}
            </Alert>
          ) : (
            <Alert 
              severity="success" 
              variant="filled"
              action={
                <IconButton size="small" color="inherit" onClick={this.handleCloseSnackbar}>
                  <CloseIcon fontSize="small" />
                </IconButton>
              }
            >
              Room found! Joining now...
            </Alert>
          )}
        </Snackbar>
      </>
    );
  }

  handleTextFieldChange(e) {
    const roomCode = e.target.value;
    const validCode = this.validateRoomCode(roomCode);
    
    this.setState({
      roomCode,
      validCode,
      error: "",
    });
  }

  roomButtonPressed() {
    const { roomCode } = this.state;
    
    // Validation before sending request
    if (!roomCode) {
      this.setState({ error: "Please enter a room code." });
      return;
    }

    if (!this.validateRoomCode(roomCode)) {
      this.setState({ error: "Room code must be 4-8 alphanumeric characters." });
      return;
    }

    // Set loading state
    this.setState({ isLoading: true, error: "" });

    const requestOptions = {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code: roomCode,
      }),
    };

    fetch("/api/join-room", requestOptions)
      .then((response) => {
        if (response.ok) {
          // Show success message before redirecting
          this.setState({ showSuccess: true, isLoading: false });
          
          // Delay redirect for a moment to show success message
          setTimeout(() => {
            this.props.history.push(`/room/${roomCode}`);
          }, 1500);
          
        } else if (response.status === 404) {
          this.setState({ 
            error: "Room not found. Please check the code and try again.", 
            isLoading: false 
          });
        } else {
          this.setState({ 
            error: "Failed to join the room. Please try again.", 
            isLoading: false 
          });
        }
      })
      .catch((error) => {
        console.error("Error joining room:", error);
        this.setState({ 
          error: "Network error. Please check your connection and try again.", 
          isLoading: false 
        });
      });
  }
}

export default withRouter(RoomJoinPage);
