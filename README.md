# Fausee - Face Verification & Monitoring System

A comprehensive face recognition and monitoring system that tracks user presence, screen time, and active time using AI-powered face detection. The system provides both desktop (Electron) and web interfaces for monitoring and analytics.

## 🎯 System Overview

Fausee is a sophisticated monitoring application that combines:
- **Face Recognition**: AI-powered face detection using InsightFace
- **Session Monitoring**: Tracks Windows session lock/unlock events
- **Usage Analytics**: Calculates screen time, active time, and monitoring statistics
- **Multi-Interface**: Electron desktop app + Flask web interface
- **Real-time Dashboard**: Live monitoring status and historical data visualization

## 🏗️ Architecture

### Core Components

1. **FaceRecognitionManager** (`face_recognition_manager.py`)
   - Handles face detection and recognition using InsightFace
   - Manages reference image capture and embedding
   - Monitors camera accessibility and session events
   - Supports both reference-based and presence-only monitoring modes

2. **MonitorAppController** (`app.py`)
   - Central orchestrator for all system components
   - Manages authentication state and monitoring lifecycle
   - Coordinates between face recognition, logging, and UI components
   - Handles background log analysis and data aggregation

3. **Database Manager** (`db_manager.py`)
   - SQLite-based data storage for users and usage statistics
   - Manages user authentication and session data
   - Stores daily monitoring metrics (screen time, active time, etc.)

4. **Log Analyzer** (`log_analyzer.py`)
   - Processes system logs to calculate usage statistics
   - Aggregates monitoring data by time intervals
   - Handles session lock/unlock event parsing

5. **Web Interface** (`flask_app.py` + `controller_api.py`)
   - Flask-based web server for authentication and API endpoints
   - RESTful API for monitoring control and data retrieval
   - Embedded dashboard UI for real-time monitoring

6. **Desktop Interface** (`electron/`)
   - Electron wrapper for native desktop experience
   - Launches Python backend and serves web interface
   - Provides system tray integration and native window management

## 🚀 Features

### Face Recognition
- **Reference Mode**: Monitors for specific authorized user using captured reference image
- **Presence Mode**: General presence detection without specific user identification
- **Real-time Processing**: Continuous camera monitoring with configurable intervals
- **Session Awareness**: Integrates with Windows session events (lock/unlock)

### Monitoring & Analytics
- **Screen Time Tracking**: Calculates actual screen usage time
- **Active Time Monitoring**: Tracks when user is actively present
- **Session Lock Detection**: Automatically detects when system is locked/unlocked
- **Historical Data**: Stores and retrieves usage statistics by date ranges
- **Real-time Dashboard**: Live status updates and data visualization

### User Interface
- **Electron Desktop App**: Native desktop application with system integration
- **Web Dashboard**: Browser-based interface accessible at `http://127.0.0.1:5000/ui`
- **Authentication System**: User registration and login with secure session management
- **Responsive Design**: Works on desktop and mobile browsers

### System Integration
- **Windows Session Events**: Monitors system lock/unlock events
- **Camera Management**: Handles camera accessibility and retry logic
- **Background Processing**: Non-blocking monitoring with background log analysis
- **Error Recovery**: Automatic restart mechanisms for monitoring loops

## 📋 Prerequisites

- **Python 3.8+**
- **Windows 10/11** (for session monitoring features)
- **Webcam** (for face recognition)
- **Node.js** (for Electron desktop app)

## 🛠️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd Fausee_Master/fausee
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

**Note**: The requirements.txt file needs to be updated to include Flask dependencies:
```bash
pip install flask flask-cors
```

### 3. Install Electron Dependencies
```bash
cd fausee_app/electron
npm install
```

## 🚀 Usage

### Desktop Application (Recommended)
```bash
cd fausee_app/electron
npm start
```

This launches the Electron desktop app which:
1. Starts the Python backend server
2. Opens the monitoring dashboard
3. Provides native desktop integration

### Web Interface Only
```bash
cd fausee_app
python app.py
```

Then open `http://127.0.0.1:5000/ui` in your browser.

### First-Time Setup

1. **Register User**: Visit `http://127.0.0.1:5000/register` to create an account
2. **Login**: Authenticate at `http://127.0.0.1:5000/login`
3. **Capture Reference Image**: Use the "Update Reference Image" button to capture your face
4. **Start Monitoring**: Choose between reference mode (specific user) or presence mode (general detection)

## 📊 Dashboard Features

### Control Panel
- **Start Monitoring (Reference)**: Monitor for specific authorized user
- **Start Monitoring (Presence)**: General presence detection
- **Stop Monitoring**: Pause all monitoring activities
- **Update Reference Image**: Capture new reference face image
- **Open Login**: Access authentication interface

### Analytics Dashboard
- **Real-time Status**: Current authentication and monitoring state
- **Usage Statistics**: Daily monitoring data with filtering options
- **Time Tracking**: Screen time and active time calculations
- **Historical Data**: View trends over different time periods

### Data Filters
- **All Time**: Complete historical data
- **Today**: Current day's statistics
- **This Week**: Weekly aggregated data
- **This Month**: Monthly aggregated data

## 🔧 Configuration

### Environment Variables
- `ELECTRON`: Set to "0" to disable Electron and use web-only mode
- `ProgramData`: Directory for storing application data (defaults to system ProgramData)

### Monitoring Settings
- **Similarity Threshold**: `SIMILARITY_THRESHOLD = 0.5` (face recognition sensitivity)
- **Frame Resolution**: `FRAME_RESIZE = (640, 480)` (camera capture resolution)
- **Detection Size**: `DET_SIZE = (320, 320)` (face detection processing size)
- **Retry Intervals**: Configurable delays for camera and recognition retries

## 📁 File Structure

```
fausee_app/
├── app.py                 # Main application controller
├── face_recognition_manager.py  # Face detection and recognition
├── db_manager.py          # Database operations
├── log_analyzer.py        # Log processing and analytics
├── flask_app.py           # Web authentication interface
├── controller_api.py      # REST API endpoints
├── gui_app.py            # Legacy Tkinter interface
├── logger_manager.py      # Logging utilities
├── electron/              # Desktop application
│   ├── main.js           # Electron main process
│   └── package.json      # Node.js dependencies
└── templates/            # Web interface templates
    ├── login.html        # Login page
    ├── register.html     # Registration page
    └── success.html      # Success confirmation
```

## 🔍 Monitoring Modes

### Reference Mode
- Captures and stores a reference face image
- Continuously monitors for the specific authorized user
- Provides high accuracy for user-specific monitoring
- Requires initial face capture setup

### Presence Mode
- General presence detection without specific user identification
- Monitors for any human face presence
- Useful for general attendance or presence tracking
- No reference image required

## 📈 Data Analytics

The system automatically calculates and stores:
- **Total Monitored Time**: Duration monitoring was active
- **Screen Time**: Total monitored time minus locked time
- **Active Time**: Screen time minus camera inaccessible periods
- **Session Events**: Lock/unlock event timestamps
- **Camera Status**: Accessibility and error tracking

## 🛡️ Security Features

- **Local Authentication**: User credentials stored locally
- **Session Management**: Secure session handling with Flask
- **Local Data Storage**: All data stored on local machine
- **No Cloud Dependencies**: Complete offline operation
- **Privacy-First**: No data transmitted to external servers

## 🔧 Troubleshooting

### Common Issues

1. **Camera Not Accessible**
   - Check camera permissions
   - Ensure no other application is using the camera
   - Verify camera drivers are installed

2. **Face Recognition Not Working**
   - Ensure good lighting conditions
   - Check camera quality and positioning
   - Update reference image if needed

3. **Electron App Not Starting**
   - Verify Node.js is installed
   - Check Python dependencies are installed
   - Ensure port 5000 is available

4. **Database Errors**
   - Check write permissions in ProgramData directory
   - Verify SQLite is working properly
   - Check disk space availability

### Log Files
- Application logs are stored in the system's ProgramData directory
- Check logs for detailed error information
- Log rotation and cleanup is handled automatically

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review application logs
3. Create an issue in the repository
4. Contact the development team

---

**Note**: This system is designed for legitimate monitoring purposes. Ensure compliance with local privacy laws and obtain proper consent before monitoring individuals.
