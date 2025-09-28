# Mesh Network Visualizer

A FastAPI-based REST server for managing mesh networks with nodes and hubs.

## Features

- Create and manage mesh networks
- Add nodes to meshes with multiple network addresses
- Promote nodes to hubs for network coordination
- Create spoke connections between nodes and hubs
- Interactive web interface for visualization and management
- Full REST API with automatic OpenAPI documentation
- SQLite database for persistent storage
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
├── main.py          # FastAPI application
├── models.py        # Database and API models
├── database.py      # Database configuration
├── run.py           # Server runner
├── requirements.txt # Dependencies
├── templates/       # HTML frontend
│   └── index.html
└── tests/           # Unit tests
    ├── __init__.py
    ├── test_base.py
    ├── test_integration.py
    ├── test_simple.py
    └── test_unit.py
```