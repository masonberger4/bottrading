# threads.md - standing threads (the live thread list is the source for everything else)
The live thread list (list_threads) is the source for which threads exist, their state and their ids. This file no longer keeps a table of all threads (the old rows, last updated 2026-11-04, are in git history). Check remote_control_status before touching the laptop; there is no standing laptop writer.
Standing threads (keep open), as of 2026-11-16:
| Run memory curator, part 2 | cmsg_01FAHERC1Lsrg2bYtrKuRHmP8ByRFuz3GAUH6LCn57dcHa | curator (ACL writer): applies memory changes, opens PRs into memory, Mase merges. Mase asked 2026-11-16 for a fresh "part 3"; handoff /mnt/project-files/mentorship/handoff_curator_2026-11-16.md | cloud |
| Daily memory dreaming pass | cmsg_01FAHERC1Lsrg2bYtrKuRHmPKCMW7kWk22AF8gP9oPxCsb | dreamer routine, proposals only; weekly, Mondays 06:05 UTC (Mase 2026-11-16) | cloud |
| Add hourly laptop session check | cmsg_01FAHERC1Lsrg2bYtrKuRHmPDBXsN7nFpUcusSMHygT1Df | hourly check that the laptop session is up; asks the coordinator to nudge it | cloud |
