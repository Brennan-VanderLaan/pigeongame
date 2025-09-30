# Mesh Network Visualizer

A FastAPI-based REST server for managing mesh networks with nodes and hubs, featuring both a web interface and a kubectl-style CLI.

## Features

- Create and manage mesh networks
- Add nodes to meshes with multiple network addresses
- Promote nodes to hubs for network coordination
- Create spoke connections between nodes and hubs
- Interactive web interface for visualization and management
- kubectl-style CLI for operators and automation (ish)
- Full REST API with automatic OpenAPI documentation
- SQLite database for persistent storage
- Structured logging
- Comprehensive unit tests

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python run.py
```

The server will start on `http://localhost:8000`

## CLI Usage

The mesh network CLI provides a kubectl-style interface for managing mesh networks from the command line.

### Basic CLI Usage

```bash
# Get help
python mesh_cli.py --help

# List all meshes (table format)
python mesh_cli.py get meshes

# List all meshes (JSON format)
python mesh_cli.py --output json get meshes
python mesh_cli.py -o json get meshes

# Create a new mesh
python mesh_cli.py create mesh production-mesh

# Get specific mesh details
python mesh_cli.py get mesh production-mesh

# Delete a mesh
python mesh_cli.py delete mesh production-mesh
```

### Node Management

```bash
# Create a node with addresses
python mesh_cli.py create node web-server-1 \
  --mesh production-mesh \
  --addrs "192.168.1.10,10.0.0.10"

# Create a node with JSON metadata
python mesh_cli.py create node db-server-1 \
  --mesh production-mesh \
  --addrs "192.168.1.20" \
  --data '{"role": "database", "cpu": 8, "memory": "32GB"}'

# List all nodes in a mesh
python mesh_cli.py get nodes --mesh production-mesh

# Get specific node details
python mesh_cli.py get node web-server-1 --mesh production-mesh

# Delete a node
python mesh_cli.py delete node web-server-1 --mesh production-mesh
```

### Hub Management

```bash
# Create a hub from an existing node
python mesh_cli.py create hub web-server-1 --mesh production-mesh

# List all hubs in a mesh
python mesh_cli.py get hubs --mesh production-mesh

# Delete a hub (node remains)
python mesh_cli.py delete hub web-server-1 --mesh production-mesh
```

### Link Management

```bash
# Connect a node to a hub (spoke connection)
python mesh_cli.py apply link \
  --mesh production-mesh \
  --node db-server-1 \
  --hub web-server-1

# Connect two hubs together
python mesh_cli.py apply hub-link \
  --mesh production-mesh \
  --source-hub web-server-1 \
  --target-hub api-server-1

# Remove a spoke connection
python mesh_cli.py delete link \
  --mesh production-mesh \
  --node db-server-1 \
  --hub web-server-1

# Disconnect two hubs
python mesh_cli.py delete hub-link \
  --mesh production-mesh \
  --source-hub web-server-1 \
  --target-hub api-server-1
```

### Global Options

```bash
# Output formats
--output json    # JSON output (clean for scripting)
--output table   # Human-readable table (default)
-o json          # Short form

# Verbosity control
--verbose        # Show debug information
-v               # Short form
--quiet          # Suppress all logs except errors
-q               # Short form

# Examples
python mesh_cli.py -v get meshes              # Verbose output
python mesh_cli.py -q -o json get meshes     # Quiet JSON output
python mesh_cli.py --verbose create mesh test # Debug mode
```

### CLI Exit Codes

- `0`: Success
- `1`: General error or validation failure
- `2`: Argument parsing error
- `409`: Resource already exists (conflict)

### Automation and Scripting

The CLI is designed for automation with clean JSON output:

```bash
# Get mesh count
mesh_count=$(python mesh_cli.py -q -o json get meshes | jq length)

# Check if mesh exists
if python mesh_cli.py -q get mesh production-mesh >/dev/null 2>&1; then
    echo "Mesh exists"
else
    echo "Creating mesh..."
    python mesh_cli.py -q create mesh production-mesh
fi

# List all node names in a mesh
python mesh_cli.py -q -o json get nodes --mesh production-mesh | \
    jq -r '.[].name'
```

## API Documentation

Once the server is running, visit:
- Interactive API docs: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`
- Web interface: `http://localhost:8000`

## API Endpoints

### Mesh Management
- `POST /mesh` - Create a new mesh
- `GET /mesh` - List all meshes
- `GET /mesh/{mesh_id}` - Get specific mesh
- `DELETE /mesh/{mesh_id}` - Delete mesh

### Node Management
- `POST /mesh/{mesh_id}/node` - Add node to mesh
- `DELETE /mesh/{mesh_id}/node/{node_id}` - Remove node from mesh

### Hub Management
- `POST /mesh/{mesh_id}/hub` - Create hub from existing node
- `GET /mesh/{mesh_id}/hub` - List hubs in mesh
- `DELETE /mesh/{mesh_id}/hub/{hub_id}` - Remove hub

### Link Management
- `POST /mesh/{mesh_id}/link_to_hub` - Connect node to hub
- `POST /mesh/{mesh_id}/unlink_from_hub` - Disconnect node from hub

## Data Models

### Mesh
- `id`: UUID
- `name`: string
- `nodes`: list of nodes
- `hubs`: list of hubs

### Node
- `id`: UUID
- `name`: string
- `addrs`: list of network addresses

### Hub
- `id`: UUID
- `name`: string (inherited from node)
- `node_id`: UUID of the underlying node
- `spokes`: list of connected nodes

## Testing

Run the test suite:
```bash
pytest tests/
```

## Development

The server uses:
- FastAPI for the REST API
- SQLAlchemy with async SQLite for data persistence
- Pydantic for data validation
- pytest for testing
- uvicorn for the ASGI server

File structure:
```
viz/
├── main.py              # FastAPI application
├── mesh_cli.py          # kubectl-style CLI interface
├── mesh_manager.py      # Core business logic library
├── models.py            # Database and API models
├── database.py          # Database configuration
├── logging_config.py    # Structured logging system
├── run.py               # Server runner
├── requirements.txt     # Dependencies
├── templates/           # HTML frontend
│   └── index.html
└── tests/               # Unit tests
    ├── __init__.py
    ├── test_base.py
    ├── test_cli.py          # CLI integration tests
    ├── test_integration.py
    ├── test_mesh_manager.py # Core library tests
    ├── test_simple.py
    └── test_unit.py
```