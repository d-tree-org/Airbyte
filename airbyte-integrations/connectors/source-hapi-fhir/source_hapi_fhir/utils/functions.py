from typing import List, Dict, Any

def flatten_dict(link_ids_to_keep: Dict[str, List[str]]) -> List[str]:
    return (
        [item for key, value in link_ids_to_keep.items() 
         if key != 'no-page' for item in ([key] + value)] +
        link_ids_to_keep.get('no-page', [])
    )

def process_data(data: Dict[str, Any], tags_to_remove: List[str] = [], link_ids_to_keep: Dict[str, List[str]] = {}) -> Dict[str, Any]:
    for tag in tags_to_remove:
        data.pop(tag, None)
    
    if 'item' in data:
        flat_list = flatten_dict(link_ids_to_keep)
        data['item'] = [
            nested_item for nested_item in data['item']
            if 'linkId' in nested_item and nested_item['linkId'] in flat_list
        ]
    
    for value in data.values():
        if isinstance(value, list):
            for nested_item in value:
                if isinstance(nested_item, dict):
                    process_data(nested_item, tags_to_remove, link_ids_to_keep)
        elif isinstance(value, dict):
            process_data(value, tags_to_remove, link_ids_to_keep)
    
    return data