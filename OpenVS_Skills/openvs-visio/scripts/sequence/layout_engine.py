from sequence.models import SequenceData

# Layout constants (inches)
PARTICIPANT_SPACING = 2.5    # horizontal distance between participants
MARGIN_LEFT = 2.0            # left margin
MARGIN_TOP = 1.5             # top margin (below participant boxes)
MESSAGE_SPACING = 0.85       # vertical distance between messages
FIRST_MESSAGE_OFFSET = 0.5   # gap between participant boxes and first message
PARTICIPANT_BOX_WIDTH = 1.4
PARTICIPANT_BOX_HEIGHT = 0.5
FRAGMENT_PADDING = 0.3       # padding around fragment boxes


def compute_layout(data: SequenceData) -> SequenceData:
    """Compute positions for participants, messages, and fragments."""
    # Participants: horizontal equally spaced
    for i, p in enumerate(data.participants):
        p.x = MARGIN_LEFT + i * PARTICIPANT_SPACING

    # Messages: vertical equally spaced from top
    for i, m in enumerate(data.messages):
        m.y = MARGIN_TOP + PARTICIPANT_BOX_HEIGHT + FIRST_MESSAGE_OFFSET + i * MESSAGE_SPACING

    # Fragments: compute y range from contained messages
    for frag in data.fragments:
        start_msg = data.get_message(frag.start_msg_id)
        end_msg = data.get_message(frag.end_msg_id)
        if start_msg and end_msg and start_msg.y is not None and end_msg.y is not None:
            frag.start_y = start_msg.y - FRAGMENT_PADDING
            frag.end_y = end_msg.y + FRAGMENT_PADDING
        elif start_msg and start_msg.y is not None:
            frag.start_y = start_msg.y - FRAGMENT_PADDING
            frag.end_y = start_msg.y + MESSAGE_SPACING
        else:
            frag.start_y = MARGIN_TOP
            frag.end_y = MARGIN_TOP + MESSAGE_SPACING

    return data
