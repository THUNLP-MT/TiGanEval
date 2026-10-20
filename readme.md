<p align="center">
  <img src="assets/logo.png" alt="TiGanEval logo" width="180">
</p>

<h1 align="center">TiGanEval</h1>

**Instructions Are Evidence, Not Objectives: Measuring Outcome Alignment of Agents**

[Paper](https://arxiv.org/abs/2610.17757) · [Tasks](tasks)

TiGanEval evaluates **outcome alignment**: whether an agent can infer what a project requires from incomplete user instructions and project evidence, and deliver a result that satisfies those requirements. The simulated user knows only part of the requirements. The agent can inspect the workspace, replay records, run experiments, and ask the user questions before submitting its work.

The benchmark contains 40 software engineering tasks and 24 research tasks. Each task has five fixed, binary requirements. A submission receives a **Score** equal to the fraction passed; **Success** requires all five. After an unsuccessful submission, the highest-priority violated requirement selects an authored observation of its consequences. The simulated user sees that observation and provides the next instruction.

## Setup

Python 3.11 or later and [uv](https://docs.astral.sh/uv/) are required. Candidate programs run under macOS Seatbelt (`sandbox-exec`) or Linux [bubblewrap](https://github.com/containers/bubblewrap). On Debian or Ubuntu, install bubblewrap with `sudo apt install bubblewrap`. Linux must permit its user namespaces and seccomp filter; unsupported environments stop with an infrastructure error.

```bash
git clone git@github.com:THUNLP-MT/TiGanEval.git
cd TiGanEval
uv sync
uv run tiganeval sandbox-check
```

## Run an evaluation

The runner uses the `openai` Python SDK and the Chat Completions interface. The endpoint must support function calling. Set your API key and select the agent model:

```bash
export OPENAI_API_KEY="your-api-key"
uv run tiganeval run \
  --model your-agent-model \
  --tasks SWE-implicit-method-routing \
  --output runs/example
```

This runs Partial and Full on the selected task. Omit `--tasks` to evaluate all 64 tasks, or use `--domain SWE` / `--domain Research`. `uv run tiganeval list` prints the task names.

The user simulator defaults to `gpt-5.6-terra`, as in the paper. Use `--user-model` to select another simulator. API model identifiers must match the names available at your endpoint. Sampling parameters are left at the endpoint defaults unless explicitly configured.

For a custom OpenAI-compatible endpoint, set `OPENAI_BASE_URL` or pass `--base-url`. The simulator inherits the agent's endpoint and API key environment variable unless overridden:

```bash
export AGENT_API_KEY="your-agent-api-key"
export USER_API_KEY="your-user-api-key"
uv run tiganeval run \
  --model your-agent-model \
  --base-url https://your-agent-endpoint.example/v1 \
  --api-key-env AGENT_API_KEY \
  --user-model your-user-model \
  --user-base-url https://your-user-endpoint.example/v1 \
  --user-api-key-env USER_API_KEY \
  --output runs/custom
```

Alternatively, copy [configs/example.yaml](configs/example.yaml) to `config.local.yaml`, set the model names and endpoints, and run:

```bash
uv run tiganeval run --config config.local.yaml --output runs/configured
```

Each model configuration accepts `model`, `base_url`, `api_key_env`, and an optional `parameters` mapping for endpoint-specific request options. API keys are read from the named environment variables. Command-line model settings override the configuration file.

## Evaluation settings

| Mode | Initial instruction | Policy | Maximum submissions |
| --- | --- | --- | ---: |
| `partial` | Partial | Infer requirements from instructions and project evidence | 4 |
| `full` | Full specification | Same policy as Partial | 1 |
| `literal` | Partial | Execute only explicit requests, including later user feedback | 4 |

Every episode has 120 turns and 360 project tool calls.

```bash
uv run tiganeval run --model your-agent-model \
  --modes partial full literal --output runs/comparison
```

## Results

```bash
uv run tiganeval report runs/example
```

To continue a run, repeat its command with the same output directory and add `--resume`. Completed episodes are skipped. Interrupted or failed attempts are preserved under `attempts/` before being restarted.

## Citation

```bibtex
@misc{liu2026tiganeval,
  title={Instructions Are Evidence, Not Objectives: Measuring Outcome Alignment of Agents},
  author={Kaiming Liu and Yuxuan Liu and Jinrui Ju and Minyuan Ruan and Xuanyu Lei and Peng Li and Yang Liu},
  year={2026},
  eprint={2610.17757},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2610.17757},
}
```

## License

[MIT](LICENSE).
