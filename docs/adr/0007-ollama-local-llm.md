# 0007. Local LLM via Ollama

- Status: accepted
- Date: 2026-10-06

## Context

Financial data must never leave the host. The machine has an RTX 5070 Laptop GPU with 8 GB VRAM.

## Decision

GenAI features use Ollama with quantised ~7–8B models; the LLM only queries a read-only analytics schema.

## Alternatives rejected

Cloud LLM APIs.

## Consequences

Model quality is limited; prompts and tools must be narrow and validated.
