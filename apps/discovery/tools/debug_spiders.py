"""Spider discovery debugging script."""

def debug_spiders():
    """Debug spider discovery."""
    print("Discovery Spider Debug")
    print("=====================")
    
    from importlib import import_module
    from inspect import isclass
    
    # Print module path
    from discovery import spiders
    print(f"Spiders module path: {spiders.__file__}")
    
    # Check Python path
    import sys
    print("\nPython path:")
    for p in sys.path:
        print(f"  {p}")
    
    # Print spider discovery
    print("\nDiscovered spiders:")
    found = {}
    module = import_module('discovery.spiders')
    for item in dir(module):
        obj = getattr(module, item)
        if isclass(obj) and hasattr(obj, 'name'):
            print(f"  {obj.name}: {obj.__module__}.{obj.__name__}")
            found[obj.name] = obj
            
    print(f"\nTotal spiders found: {len(found)}")
    
if __name__ == '__main__':
    debug_spiders()
