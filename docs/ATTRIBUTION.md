# Attribution

JobPilot incorporates techniques and adapted code from the following open-source
projects. We are grateful to their authors.

## ai-job-search

- **Repository:** https://github.com/MadsLorentzen/ai-job-search
- **License:** MIT
- **Author:** Mads Lorentzen

The following JobPilot components adapt ideas and/or code from `ai-job-search`:

| JobPilot component | Adapted from |
|--------------------|--------------|
| `backend/app/automation/linkedin/guest.py` | The `linkedin-search` skill (LinkedIn public `jobs-guest` endpoints, HTML parsing). Ported from TypeScript to Python. |
| `backend/app/automation/pipeline/scorer.py` | The 5-dimension job-evaluation framework (`04-job-evaluation.md`): technical/experience/behavioral/career weighting + location veto. |
| `backend/app/automation/pipeline/ats.py` | The ATS keyword-coverage verification concept (`/apply` workflow). |
| `backend/app/automation/writing_style.py` and `content.py` | The writing-style guide (`03-writing-style.md`) and the drafter-reviewer workflow (`/apply`). |

The underlying `linkedin-search` job-search CLI skills in `ai-job-search` are
themselves credited to Mikkel Krogholm (https://github.com/mikkelkrogsholm/skills).

### MIT License (ai-job-search)

```
MIT License

Copyright (c) MadsLorentzen

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Note on LinkedIn usage

The `jobs-guest` and Voyager endpoints are used for personal, low-volume job
search only. Automated access is against LinkedIn's Terms of Service; use
responsibly and at your own risk, ideally with a dedicated account.
