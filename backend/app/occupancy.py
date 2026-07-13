# TODO: PIR OUTSIDE -> INSIDE sequence detection (entry inference)
# TODO: PIR INSIDE -> OUTSIDE sequence detection (exit inference)
# TODO: mmWave trajectory analysis for occupancy inference
# TODO: CO2 trend analysis as a secondary occupancy signal
# TODO: Duplicate-event filtering (debounce repeated triggers)
# TODO: Sensor health monitoring (detect stale / offline devices)

_ENTRY_EVENT = "ENTRY"
_EXIT_EVENT = "EXIT"


def compute_new_count(current_count: int, event_type: str, event_count: int) -> int:
    if event_type == _ENTRY_EVENT:
        return current_count + event_count
    if event_type == _EXIT_EVENT:
        return max(0, current_count - event_count)
    return current_count


def get_occupancy_level(count: int) -> str:
    if count == 0:
        return "Empty"
    if count <= 5:
        return "Low"
    if count <= 15:
        return "Medium"
    return "High"
