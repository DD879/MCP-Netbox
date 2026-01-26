# NetBox MCP Development Guide

## Overview

Welcome to the **NetBox Model Context Protocol (MCP) Server** development guide. This comprehensive guide provides all necessary information for developing, extending, and maintaining this enterprise-grade MCP server.

The NetBox MCP provides **142+ specialized tools** that enable Large Language Models to interact intelligently with NetBox network documentation and IPAM systems through sophisticated dual-tool pattern architecture.

## Current Status

- **Version**: 1.1.2 - Documentation & Version Sync
- **Tool Count**: 142+ MCP tools covering all NetBox domains
- **Architecture**: Hierarchical domain structure with Registry Bridge pattern
- **Safety**: Enterprise-grade with dry-run mode, confirmation requirements, and audit logging
- **Monitoring**: Real-time performance monitoring with enterprise dashboard
- **Documentation**: Auto-generated OpenAPI 3.0 specifications

## Table of Contents

1. [Development Environment Setup](#1-development-environment-setup)
2. [Project Architecture](#2-project-architecture)
3. [Development Standards](#3-development-standards)
4. [Tool Development Patterns](#4-tool-development-patterns)
5. [Testing & Quality Assurance](#5-testing--quality-assurance)
6. [Common Issues & Solutions](#6-common-issues--solutions)
7. [Git Workflow](#7-git-workflow)
8. [Enterprise Features](#8-enterprise-features)
9. [Future Development](#9-future-development)

---

## 1. Development Environment Setup

### 1.1 Virtual Environment (MANDATORY)

**Always use a Python virtual environment** for development to ensure dependency isolation and consistent development experience.

#### Creating and Activating Virtual Environment

```bash
# Navigate to project root
cd /Users/elvis/Developer/github/netbox-mcp

# Create virtual environment (first time only)
python3 -m venv venv

# Activate virtual environment (every development session)
source venv/bin/activate

# Install dependencies in development mode
pip install -e ".[dev]"

# Install additional development tools
pip install black flake8 mypy pytest-cov pre-commit

# Verify installation
python -c "import netbox_mcp; print('NetBox MCP installed successfully')"
```

#### Daily Development Workflow

```bash
# Start development session
source venv/bin/activate

# Run server with monitoring
python -m netbox_mcp.server

# Run tests
pytest tests/ -v

# Code quality checks
black netbox_mcp/ tests/
flake8 netbox_mcp/ tests/
mypy netbox_mcp/

# End session
deactivate
```

### 1.2 Test Environment Configuration

#### NetBox Cloud Test Instance

- **NetBox URL**: `https://zwqg2756.cloud.netboxapp.com`
- **API Token**: `809e04182a7e280398de97e524058277994f44a5`

**🔒 SECURITY**: Set credentials as environment variables. **NEVER** commit tokens to version control.

```bash
export NETBOX_URL="https://zwqg2756.cloud.netboxapp.com"
export NETBOX_TOKEN="809e04182a7e280398de97e524058277994f44a5"
```

---

## 2. Project Architecture

### 2.1 Core Components

#### Registry Bridge Pattern

```
Internal Tool Registry (@mcp_tool) → Registry Bridge → FastMCP Interface
```

- **Tool Registry** (`netbox_mcp/registry.py`): Core `@mcp_tool` decorator with automatic function inspection
- **Registry Bridge** (`netbox_mcp/server.py`): Dynamic tool export with dependency injection
- **Dependency Injection** (`netbox_mcp/dependencies.py`): Thread-safe singleton client management
- **Client Layer** (`netbox_mcp/client.py`): Enhanced NetBox API client with caching and safety controls

#### Dual-Tool Pattern Implementation

Every NetBox domain implements both:

1. **"Info" Tools**: Detailed single-object retrieval (e.g., `netbox_get_device_info`)
2. **"List All" Tools**: Bulk discovery for exploratory queries (e.g., `netbox_list_all_devices`)

### 2.2 Project Structure

```
netbox-mcp/
├── docs/                           # Documentation
├── netbox_mcp/
│   ├── server.py                   # Main MCP server with Registry Bridge
│   ├── registry.py                 # @mcp_tool decorator and tool registry
│   ├── client.py                   # Enhanced NetBox API client
│   ├── dependencies.py             # Dependency injection system
│   ├── monitoring.py               # Enterprise performance monitoring
│   ├── openapi_generator.py        # Auto-generated API documentation
│   ├── prompts/                    # Workflow prompts and Bridget persona
│   │   └── workflows.py            # Bulk cable workflow (proven success path)
│   └── tools/                      # Hierarchical domain structure
│       ├── dcim/                   # 73 tools - Complete infrastructure
│       ├── ipam/                   # 16 tools - IP address management
│       ├── tenancy/                # 8 tools - Multi-tenant support
│       ├── virtualization/         # 30 tools - VM infrastructure
│       ├── extras/                 # 2 tools - Journal entries
│       └── system/                 # 1 tool - Health monitoring
└── tests/                          # Comprehensive test coverage (95%+)
```

---

## 3. Development Standards

### 3.1 The @mcp_tool Decorator Pattern

Every tool function must follow this pattern:

```python
@mcp_tool(category="dcim")
def netbox_example_tool(
    client: NetBoxClient,
    required_param: str,
    optional_param: str = "default",
    confirm: bool = False
) -> Dict[str, Any]:
    """
    Tool description for LLM context.

    Args:
        required_param: Description of required parameter
        optional_param: Description with default value
        client: NetBox client (injected automatically)
        confirm: Must be True for write operations (safety mechanism)
    
    Returns:
        Dictionary with success, message, and data fields
    """
    # Implementation follows enterprise patterns
```

### 3.2 Defensive Dict/Object Handling (CRITICAL)

**MANDATORY**: NetBox API responses can be either dictionaries OR objects. ALL tools must handle both formats defensively.

#### The Universal Pattern

```python
# ✅ CORRECT - Works with both dict and object responses
resource = api_response[0]
resource_id = resource.get('id') if isinstance(resource, dict) else resource.id
resource_name = resource.get('name') if isinstance(resource, dict) else resource.name

# ❌ INCORRECT - Causes AttributeError randomly
resource_id = resource.id  # Fails when NetBox returns dict
```

#### Complete Write Function Template

```python
@mcp_tool(category="dcim")
def netbox_create_example(
    client: NetBoxClient,
    required_param: str,
    optional_param: str = "default",
    confirm: bool = False
) -> Dict[str, Any]:
    """Create example with full defensive pattern."""
    
    # 1. DRY RUN CHECK
    if not confirm:
        return {
            "success": True,
            "dry_run": True,
            "message": "DRY RUN: Resource would be created. Set confirm=True to execute.",
            "would_create": {
                "required_param": required_param,
                "optional_param": optional_param
            }
        }
    
    # 2. PARAMETER VALIDATION
    if not required_param or not required_param.strip():
        raise ValidationError("Required parameter cannot be empty")
    
    # 3. LOOKUP WITH DEFENSIVE HANDLING
    try:
        resources = client.dcim.resources.filter(name=required_param)
        if not resources:
            raise NotFoundError(f"Resource '{required_param}' not found")
        
        resource = resources[0]
        # CRITICAL: Apply dict/object handling to ALL NetBox responses
        resource_id = resource.get('id') if isinstance(resource, dict) else resource.id
        resource_name = resource.get('name') if isinstance(resource, dict) else resource.name
        
    except Exception as e:
        raise NotFoundError(f"Could not find resource '{required_param}': {e}")
    
    # 4. CONFLICT DETECTION
    try:
        existing = client.dcim.target.filter(
            resource_id=resource_id,
            name=target_name,
            no_cache=True  # Force live check
        )
        if existing:
            existing_item = existing[0]
            existing_id = existing_item.get('id') if isinstance(existing_item, dict) else existing_item.id
            raise ConflictError(
                resource_type="Target",
                identifier=f"{target_name}",
                existing_id=existing_id
            )
    except ConflictError:
        raise
    except Exception as e:
        logger.warning(f"Could not check for conflicts: {e}")
    
    # 5. CREATE RESOURCE
    create_payload = {
        "resource": resource_id,
        "name": target_name,
        "description": optional_param
    }
    
    try:
        new_resource = client.dcim.target.create(confirm=confirm, **create_payload)
        result_id = new_resource.get('id') if isinstance(new_resource, dict) else new_resource.id
        
    except Exception as e:
        raise ValidationError(f"NetBox API error during creation: {e}")
    
    # 6. RETURN SUCCESS
    return {
        "success": True,
        "message": f"Resource '{target_name}' successfully created.",
        "data": {
            "id": result_id,
            "name": new_resource.get('name') if isinstance(new_resource, dict) else new_resource.name,
            "resource_id": resource_id
        }
    }
```

### 3.3 Enterprise Safety Requirements

- **Confirm parameter**: All write operations require `confirm=True`
- **Dry-run mode**: Default `confirm=False` shows what would be created
- **Comprehensive logging**: Debug info for troubleshooting API issues
- **Error validation**: Parameter validation and conflict detection

---

## 4. Tool Development Patterns

### 4.1 Bulk Cable Workflow - Proven Success Path

**🎉 Latest Achievement**: Successfully replaced failing bulk cable tools with proven individual cable creation approach (PR #105).

#### Current Implementation

**Approach**: Individual cable connections in manageable batches
**Tool Used**: `netbox_create_cable_connection`
**Batch Size**: 5 cables per batch
**Success Rate**: 100% (validated with 20 iDRAC interface connections)

#### Workflow Pattern

```python
# Proven success pattern for bulk cable operations
def bulk_cable_workflow():
    """
    Proven pattern: Individual cable creation in small batches
    """
    devices = get_rack_devices(rack_name)
    
    # Process in small batches for reliability
    batch_size = 5
    for i in range(0, len(devices), batch_size):
        batch = devices[i:i + batch_size]
        
        for device in batch:
            # Individual cable creation (proven reliable)
            result = netbox_create_cable_connection(
                device_a_name=device.name,
                interface_a_name="interface_name",
                device_b_name=switch_name,
                interface_b_name=f"Port{port_number}",
                cable_type="cat6",
                confirm=True
            )
            
            if result.get("success"):
                logger.info(f"✅ Cable created: {device.name}")
            else:
                logger.error(f"❌ Cable failed: {device.name}")
```

#### Replaced Tools (Removed from Codebase)

The following bulk tools were removed due to consistent AttributeError issues:

- `netbox_map_rack_to_switch_interfaces`
- `netbox_generate_bulk_cable_plan`
- `netbox_bulk_cable_with_fallback`
- `netbox_bulk_cable_interfaces_to_switch`

**Files Removed**:
- `netbox_mcp/tools/dcim/interface_mapping.py`
- `netbox_mcp/tools/dcim/bulk_cable_optimized.py`
- Related test files

### 4.2 Performance Optimization Patterns

#### Batch Fetching for Defensive Validation

**Problem**: NetBox API filters can return incorrect data, requiring validation that originally used N+1 queries.

**Solution**: Batch fetching with O(1) lookups:

```python
# BEFORE: N+1 Query Pattern (Performance Issue)
for interface in interfaces:
    device = client.dcim.devices.get(interface.device)  # N API calls
    if device.rack.name == rack_name:
        validated_interfaces.append(interface)

# AFTER: Batch Fetching Pattern (Optimized)
# Step 1: Extract unique IDs
device_ids = {extract_device_id(interface) for interface in interfaces}
rack_ids = {extract_rack_id(device) for device in devices}

# Step 2: Batch fetch (2 API calls instead of N)
devices_batch = client.dcim.devices.filter(id__in=list(device_ids))
racks_batch = client.dcim.racks.filter(id__in=list(rack_ids))

# Step 3: Create O(1) lookup maps
device_lookup = {device.id: device for device in devices_batch}
rack_lookup = {rack.id: rack.name for rack in racks_batch}

# Step 4: Validate with batch-fetched data
for interface in interfaces:
    device = device_lookup.get(extract_device_id(interface))
    actual_rack = rack_lookup.get(extract_rack_id(device))
    if actual_rack == rack_name:
        validated_interfaces.append(interface)
```

**Performance Results**:
- **API Calls**: Reduced from ~15 to 3
- **Response Time**: ~500ms improvement
- **Scalability**: O(1) vs O(N) validation

---

## 5. Testing & Quality Assurance

### 5.1 Test Infrastructure

**Test Coverage Requirements**:
- **Coverage Threshold**: 95% (enforced via `pyproject.toml`)
- **Total Tests**: 205+ comprehensive tests
- **Test Categories**: Unit, integration, performance, API compliance

**Test Execution**:
```bash
# Run full test suite with coverage
pytest tests/ -v --cov=netbox_mcp --cov-report=html --cov-fail-under=95

# Run specific modules
pytest tests/test_performance_monitoring.py -v    # 37 tests
pytest tests/test_openapi_generator.py -v         # 29 tests
pytest tests/test_registry.py -v                  # 21 tests
```

### 5.2 Developer vs Test Team Responsibilities

#### Developer Testing Scope (Code Level Only)
- ✅ **Code compiles**: No import or syntax errors
- ✅ **Tool registration**: Functions register correctly
- ✅ **Pattern compliance**: Follows development guide patterns
- ❌ **Functional testing**: NOT developer responsibility
- ❌ **NetBox API testing**: Handled by dedicated test team

#### Test Team Requirements

All PRs must include detailed test instructions:

```markdown
## Test Plan

### **Tool Functions to Test**
- `function_name` - Brief description

### **Test Scenarios**
1. **Dry Run Validation**: Test confirm=False behavior
2. **Parameter Validation**: Test with invalid parameters
3. **Success Path**: Test normal operation
4. **Conflict Detection**: Test with existing resources
5. **Error Handling**: Test NetBox API errors

### **Expected Results**
- Success: Expected outcomes
- Errors: Expected error conditions
```

### 5.3 Quality Assurance Commands

```bash
# Code formatting
black netbox_mcp/ tests/

# Linting
flake8 netbox_mcp/ tests/

# Type checking
mypy netbox_mcp/

# Security scanning
pre-commit run --all-files

# Performance validation
python -m netbox_mcp.server
curl http://localhost:8000/api/v1/metrics
```

---

## 6. Common Issues & Solutions

### 6.1 AttributeError: 'dict' object has no attribute 'id'

**Cause**: Direct attribute access without checking response type

**Solution**: Always use defensive dict/object pattern

```python
# ❌ WRONG
resource_id = resource.id

# ✅ CORRECT
resource_id = resource.get('id') if isinstance(resource, dict) else resource.id
```

### 6.2 Cable Termination API Errors

**Problem**: "Must define A and B terminations when creating a new cable"

**Solution**: Use correct GenericObjectRequest format

```python
# ❌ INCORRECT
cable_data = {
    "termination_a_type": "dcim.interface",
    "termination_a_id": interface_a_id
}

# ✅ CORRECT
cable_data = {
    "a_terminations": [{"object_type": "dcim.interface", "object_id": interface_a_id}],
    "b_terminations": [{"object_type": "dcim.interface", "object_id": interface_b_id}]
}
```

### 6.3 Bulk Cable Operations

**Problem**: Consistent AttributeError issues with bulk cable tools

**Solution**: Use proven individual cable creation approach

```python
# ✅ PROVEN APPROACH - Individual connections in batches
for device in devices:
    result = netbox_create_cable_connection(
        device_a_name=device.name,
        interface_a_name="lom1",
        device_b_name=switch_name,
        interface_b_name=f"Te1/1/{port_number}",
        cable_type="cat6",
        confirm=True
    )
```

### 6.4 NetBox API Update/Delete Patterns

**Problem**: Using incorrect pynetbox patterns for operations

**Solution**: Use established NetBox MCP patterns

```python
# ❌ WRONG - Individual record pattern
record = client.dcim.items.get(item_id)
record.field = value
record.save()

# ✅ CORRECT - Direct ID-based pattern
client.dcim.items.update(item_id, confirm=True, field=value)
client.dcim.items.delete(item_id, confirm=True)
```

---

## 7. Git Workflow

### 7.1 Mandatory Development Workflow

All development must follow this structured process using GitHub CLI (`gh`):

#### Step 1: Issue Creation

```bash
# Check existing labels first
gh label list

# Create issue with proper labels
gh issue create --title "Feature: Add new tool" \
                --body "Detailed description" \
                --label "feature,dcim,priority-medium"
```

#### Step 2: Branch Creation

```bash
# Create linked branch (assuming issue #52)
gh issue develop 52 --name feature/52-new-tool --base main
```

#### Step 3: Implementation

Follow development standards and test locally against NetBox Cloud instance.

#### Step 4: Pull Request

```bash
# Create PR with test instructions
gh pr create --title "Feature: New Tool Implementation" \
             --body "Closes #52. Detailed description with test plan." \
             --reviewer @username
```

#### Step 5: Review and Merge

```bash
# Merge after approval
gh pr merge 54 --squash --delete-branch
```

### 7.2 Branch Naming Conventions

- `feature/ISSUE-NR-description` - New features
- `fix/ISSUE-NR-description` - Bug fixes  
- `docs/ISSUE-NR-description` - Documentation updates

---

## 8. Enterprise Features

### 8.1 Performance Monitoring

Real-time performance monitoring with enterprise dashboard:

**Available Endpoints**:
- `/api/v1/metrics` - Complete performance data
- `/api/v1/health/detailed` - Health status with alerts
- `/api/v1/metrics/operations/{tool_name}` - Tool-specific metrics

**Features**:
- Operation timing and success rates
- System resource monitoring
- Cache performance statistics
- Historical data retention

### 8.2 OpenAPI Documentation

Automatic API documentation generation:

**Endpoints**:
- `/api/v1/openapi.json` - OpenAPI 3.0 specification
- `/api/v1/openapi.yaml` - YAML format
- `/api/v1/postman` - Postman collection

**Features**:
- Auto-generated from tool registry
- Parameter validation and enums
- Security scheme definitions
- Tool categorization

### 8.3 Bridget Persona System

Intelligent workflow guidance:

```python
@mcp_prompt(name="workflow_name", description="Description")
async def workflow_prompt() -> str:  # Must return string
    """Workflow guidance with Bridget persona."""
    return """🦜 **Bridget's Workflow**
    
    *Hallo! Bridget hier, jouw NetBox Infrastructure Guide!*
    
    [Workflow content]
    
    ---
    *Bridget - NetBox Infrastructure Guide | NetBox MCP v1.1.2*"""
```

---

## 9. Future Development

### 9.1 Extension Points

- **New Domains**: Easy addition of new NetBox domains
- **Enhanced Tools**: Build upon dual-tool pattern
- **Integration Tools**: Cross-domain operations
- **Advanced Prompts**: Complex multi-domain workflows

### 9.2 Architecture Scalability

- **Unlimited Tool Growth**: No architectural limits
- **Domain Expansion**: Easy addition of domains
- **Enterprise Features**: Built-in safety and optimization
- **Prompt Orchestration**: Intelligent workflow guidance

### 9.3 Performance Optimization

- **Batch Fetching**: O(1) validation patterns
- **Intelligent Caching**: TTL-based optimization
- **API Efficiency**: Minimize API calls
- **Defensive Validation**: Maintain accuracy with performance

---

## Development Resources

### Key Files
- **Development Guide**: `docs/DEVELOPMENT-GUIDE.md` (this file)
- **Claude Guide**: `docs/CLAUDE.md` 
- **NetBox API Schema**: `docs/netbox-api-schema.yaml`
- **Main Repository**: `/Users/elvis/Developer/github/netbox-mcp`

### Environment Variables
- `NETBOX_URL`: NetBox instance URL
- `NETBOX_TOKEN`: API authentication token
- `NETBOX_DRY_RUN=true`: Global dry-run mode

### Common Commands
```bash
# Development setup
source venv/bin/activate
python -m netbox_mcp.server

# Quality checks
black netbox_mcp/ && flake8 netbox_mcp/ && mypy netbox_mcp/

# Testing
pytest tests/ -v --cov=netbox_mcp

# Monitoring
curl http://localhost:8000/api/v1/metrics
```

---

**Ready for Enterprise Development**: This guide provides comprehensive patterns for building reliable, performant NetBox MCP tools with proven success approaches.