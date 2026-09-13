package StateDemo {
    occurrence def EngagementEvent;

    part def Surface {
        exhibit state condition {
            entry; then dormant;
            state dormant;
            state active;
            transition first dormant accept EngagementEvent then active;
        }
    }

    part surface1 : Surface;
}
