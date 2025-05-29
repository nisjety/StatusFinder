"""
Discovery Pipelines Package

This package contains all item processing pipelines for the Discovery project.
"""

# Import all available pipelines
from .mongodb import MongoPipeline
from .exporter import ExporterPipeline
from .fingerprint import ContentFingerprintPipeline
from .metadata import MetadataPipeline
from .stats import StatsPipeline
from .versioning import VersioningPipeline
from .visualize import VisualizePipeline
from .rabbitmq import RabbitMQPipeline

# Make all pipelines available at package level
__all__ = [
    'MongoPipeline',
    'ExporterPipeline', 
    'ContentFingerprintPipeline',
    'MetadataPipeline',
    'StatsPipeline',
    'VersioningPipeline',
    'VisualizePipeline',
    'RabbitMQPipeline',
]

# Pipeline registry for easy access
AVAILABLE_PIPELINES = {
    'mongodb': 'discovery.pipelines.mongodb.MongoPipeline',
    'exporter': 'discovery.pipelines.exporter.ExporterPipeline',
    'fingerprint': 'discovery.pipelines.fingerprint.ContentFingerprintPipeline',
    'metadata': 'discovery.pipelines.metadata.MetadataPipeline',
    'stats': 'discovery.pipelines.stats.StatsPipeline',
    'versioning': 'discovery.pipelines.versioning.VersioningPipeline',
    'visualize': 'discovery.pipelines.visualize.VisualizePipeline',
    'rabbitmq': 'discovery.pipelines.rabbitmq.RabbitMQPipeline',
}

def get_pipeline_class(name: str):
    """
    Get a pipeline class by name.
    
    Args:
        name: Pipeline name (e.g., 'mongodb', 'exporter')
    
    Returns:
        Pipeline class or None if not found
    """
    pipeline_map = {
        'mongodb': MongoPipeline,
        'exporter': ExporterPipeline,
        'fingerprint': ContentFingerprintPipeline,
        'metadata': MetadataPipeline,
        'stats': StatsPipeline,
        'versioning': VersioningPipeline,
        'visualize': VisualizePipeline,
        'rabbitmq': RabbitMQPipeline,
    }
    return pipeline_map.get(name)