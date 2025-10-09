# Netpalm GUI

A web-based graphical user interface for [Netpalm](https://github.com/tbotnz/netpalm) network automation platform.

## Features

- **Dashboard**: Real-time overview of workers, devices, and job queue status
- **Job Monitor**: Track task execution with auto-refresh capability
- **Config Deployment**: Deploy configurations using multiple drivers (Netmiko, NAPALM, NCCLIENT, RESTCONF)
- **Netbox Integration**: Automatically fetch device inventory from Netbox
- **Real-time Updates**: Auto-refresh capabilities for monitoring active jobs

## Architecture

- **Backend**: Flask Python web framework
- **Frontend**: Bootstrap 5 + jQuery for responsive UI
- **Integration**: Connects to Netpalm API (port 9000) and Netbox API
- **Deployment**: Docker container integrated with netpalm docker-compose

## Installation

### Prerequisites

1. Netpalm installation (docker-compose)
2. Netbox instance with API access
3. Netbox API token

### Setup

1. **Copy environment variables file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` and add your Netbox token:**
   ```bash
   NETBOX_TOKEN=your_actual_token_here
   ```

3. **Build and start all services:**
   ```bash
   docker-compose up -d --build
   ```

4. **Access the GUI:**
   Open your browser to `http://localhost:8088`

## Configuration

The GUI can be configured via environment variables in `docker-compose.yml`:

- `NETPALM_API_URL`: URL of the netpalm controller (default: `http://netpalm-controller:9000`)
- `NETBOX_URL`: URL of your Netbox instance
- `NETBOX_TOKEN`: Your Netbox API token
- `VERIFY_SSL`: Whether to verify SSL certificates for Netbox (default: `false`)

## Usage

### Dashboard
- View real-time statistics for workers, devices, and jobs
- Quick access to deployment and monitoring features

### Deploy Configuration

**Get Config (Retrieve):**
1. Select a device from the Netbox inventory
2. Choose the driver (Netmiko, NAPALM, etc.)
3. Enter the command (e.g., `show running-config`)
4. Provide credentials
5. Click "Execute"

**Set Config (Deploy):**
1. Select a device
2. Choose the driver
3. Enter configuration commands (one per line)
4. Provide credentials
5. Optionally enable "Dry Run" to validate without applying
6. Click "Deploy Configuration"

### Monitor Jobs
- View all tasks in the queue
- Filter completed tasks
- Enable auto-refresh (5 second intervals)
- View detailed task results by clicking "View"
- Monitor worker status

## API Endpoints

The GUI exposes the following internal API endpoints:

- `GET /api/devices` - Get devices from Netbox with details
- `GET /api/device-names` - Get simple list of device names
- `GET /api/tasks` - Get all tasks from netpalm
- `GET /api/task/<task_id>` - Get specific task details
- `GET /api/workers` - Get all workers
- `POST /api/deploy/getconfig` - Execute getconfig
- `POST /api/deploy/setconfig` - Execute setconfig
- `POST /api/deploy/setconfig/dry-run` - Execute setconfig dry-run

## File Structure

```
netpalm-gui/
├── app.py                 # Flask application
├── netbox_client.py       # Netbox API client
├── requirements.txt       # Python dependencies
├── Dockerfile            # Docker configuration
├── templates/            # HTML templates
│   ├── base.html
│   ├── index.html        # Dashboard
│   ├── deploy.html       # Config deployment
│   └── monitor.html      # Job monitor
└── static/               # Static assets
    ├── css/
    │   └── style.css
    └── js/
        ├── dashboard.js
        ├── deploy.js
        └── monitor.js
```

## Development

To run the GUI in development mode (outside Docker):

```bash
cd netpalm-gui
pip install -r requirements.txt

# Set environment variables
export NETPALM_API_URL=http://localhost:9000
export NETBOX_URL=https://netbox-prprd.gi-nw.viasat.io
export NETBOX_TOKEN=your_token
export VERIFY_SSL=false

# Run the app
python app.py
```

The GUI will be available at `http://localhost:8088`

## Troubleshooting

**Cannot connect to Netpalm API:**
- Ensure netpalm-controller is running
- Check that both services are on the same Docker network
- Verify NETPALM_API_URL environment variable

**Devices not loading from Netbox:**
- Verify NETBOX_TOKEN is correct
- Check Netbox URL is accessible
- Review logs: `docker-compose logs netpalm-gui`

**SSL Certificate errors:**
- For self-signed certificates, ensure `VERIFY_SSL=false` in docker-compose.yml

## License

This GUI is provided as an extension to the Netpalm project and follows the same license terms.
