import React, { Component } from "react";
import RoomJoinPage from "./RoomJoinPage";
import CreateRoomPage from "./CreateRoomPage";
import Room from "./Room";
import { 
  Grid, 
  Button, 
  Typography, 
  Card, 
  CardContent, 
  Box, 
  Fade, 
  CircularProgress,
  Container
} from "@material-ui/core";
import MusicNoteIcon from "@material-ui/icons/MusicNote";
import AddIcon from "@material-ui/icons/Add";
import GroupIcon from "@material-ui/icons/Group";
import {
  BrowserRouter as Router,
  Switch,
  Route,
  Link,
  Redirect,
} from "react-router-dom";

export default class HomePage extends Component {
  constructor(props) {
    super(props);
    this.state = {
      roomCode: null,
      loading: true
    };
    this.clearRoomCode = this.clearRoomCode.bind(this);
  }

  async componentDidMount() {
    fetch("/api/user-in-room")
      .then((response) => response.json())
      .then((data) => {
        this.setState({
          roomCode: data.code,
          loading: false
        });
      })
      .catch(error => {
        console.error("Error fetching room:", error);
        this.setState({ loading: false });
      });
  }

  renderHomePage() {
    if (this.state.loading) {
      return (
        <Box display="flex" justifyContent="center" alignItems="center" minHeight="100vh">
          <CircularProgress className="loading-pulse" size={60} />
        </Box>
      );
    }

    return (
      <Container>
        <Fade in={!this.state.loading} timeout={1000}>
          <Card className="music-card" elevation={6}>
            <CardContent>
              <Grid container spacing={4}>
                <Grid item xs={12} align="center">
                  <MusicNoteIcon style={{ fontSize: 60, color: "#1e3c72", marginBottom: 20 }} />
                  <Typography variant="h2" component="h1" className="main-title">
                    House Party
                  </Typography>
                  <Typography variant="h6" style={{ marginBottom: 30, color: "#666" }}>
                    Join the ultimate music sharing experience
                  </Typography>
                </Grid>
                
                <Grid item xs={12} sm={6} align="center">
                  <Button 
                    className="action-button join-button"
                    variant="contained" 
                    size="large"
                    startIcon={<GroupIcon />}
                    component={Link}
                    to="/join"
                    fullWidth
                  >
                    Join a Room
                  </Button>
                </Grid>
                
                <Grid item xs={12} sm={6} align="center">
                  <Button 
                    className="action-button create-button"
                    variant="contained"
                    size="large"
                    startIcon={<AddIcon />}
                    component={Link}
                    to="/create"
                    fullWidth
                  >
                    Create a Room
                  </Button>
                </Grid>
                
                <Grid item xs={12} align="center">
                  <Typography variant="body2" style={{ marginTop: 20, color: "#666" }}>
                    Control Spotify playback with friends in real-time
                  </Typography>
                </Grid>
              </Grid>
            </CardContent>
          </Card>
        </Fade>
      </Container>
    );
  }

  clearRoomCode() {
    this.setState({
      roomCode: null,
    });
  }

  render() {
    return (
      <Router>
        <div className="app-container">
          <Switch>
            <Route
              exact
              path="/"
              render={() => {
                return this.state.roomCode ? (
                  <Redirect to={`/room/${this.state.roomCode}`} />
                ) : (
                  this.renderHomePage()
                );
              }}
            />
            <Route path="/join" component={RoomJoinPage} />
            <Route path="/create" component={CreateRoomPage} />
            <Route
              path="/room/:roomCode"
              render={(props) => {
                return <Room {...props} leaveRoomCallback={this.clearRoomCode} />;
              }}
            />
          </Switch>
        </div>
      </Router>
    );
  }
}
