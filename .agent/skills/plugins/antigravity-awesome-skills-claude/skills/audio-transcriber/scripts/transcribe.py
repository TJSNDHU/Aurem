#!/usr/bin/env python3
"""
Audio Transcriber v1.1.0
Transcreve áudio para texto e gera atas/resumos usando LLM.
"""

import os
import sys
import json
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

# Rich for beautiful terminal output
try:
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    print("⚠️  Installing rich for better UI...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "rich"], check=False)
    from rich.console import Console
    from rich.prompt import Prompt
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
    from rich import print as rprint

# tqdm for progress bars
try:
    from tqdm import tqdm
except ImportError:
    print("⚠️  Installing tqdm for progress bars...")
    subprocess.run([sys.executable, "-m", "pip", "install", "--user", "tqdm"], check=False)
    from tqdm import tqdm

# Whisper engines
try:
    from faster_whisper import WhisperModel
    TRANSCRIBER = "faster-whisper"
except ImportError:
    try:
        import whisper
        TRANSCRIBER = "whisper"
    except ImportError:
        print("❌ Nenhum engine de transcrição encontrado!")
        print("   Instale: pip install faster-whisper")
        sys.exit(1)

console = Console()

# Template padrão RISEN para fallback
DEFAULT_MEETING_PROMPT = """
Role: Você é um transcritor profissional especializado em documentação.

Instructions: Transforme a transcrição fornecida em um documento estruturado e profissional.

Steps:
1. Identifique o tipo de conteúdo (reunião, palestra, entrevista, etc.)
2. Extraia os principais tópicos e pontos-chave
3. Identifique participantes/speakers (se aplicável)
4. Extraia decisões tomadas e ações definidas (se reunião)
5. Organize em formato apropriado com seções claras
6. Use Markdown para formatação profissional

End Goal: Documento final bem estruturado, legível e pronto para distribuição.

Narrowing: 
- Mantenha objetividade e clareza
- Preserve contexto importante
- Use formatação Markdown adequada
- Inclua timestamps relevantes quando aplicável
"""


def detect_cli_tool():
    """Detecta qual CLI de LLM está disponível (claude > gh copilot)."""
    if shutil.which('claude'):
        return 'claude'
    elif shutil.which('gh'):
        result = subprocess.run(['gh', 'copilot', '--version'], 
                                capture_output=True, text=True)
        if result.returncode == 0:
            return 'gh-copilot'
    return None


def invoke_prompt_engineer(raw_prompt, timeout=90):
    """
    Invoca prompt-engineer skill via CLI para melhorar/gerar prompts.
    
    Args:
        raw_prompt: Prompt a ser melhorado ou meta-prompt
        timeout: Timeout em segundos
    
    Returns:
        str: Prompt melhorado ou DEFAULT_MEETING_PROMPT se falhar
    """
    try:
        # Tentar via gh copilot
        console.print("[dim]   Invocando prompt-engineer...[/dim]")
        
        result = subprocess.run(
            ['gh', 'copilot', 'suggest', '-t', 'shell', raw_prompt],
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
        else:
            console.print("[yellow]⚠️  prompt-engineer não respondeu, usando template padrão[/yellow]")
            return DEFAULT_MEETING_PROMPT
            
    except subprocess.TimeoutExpired:
        console.print(f"[red]⚠️  Timeout após {timeout}s, usando template padrão[/red]")
        return DEFAULT_MEETING_PROMPT
    except Exception as e:
        console.print(f"[red]⚠️  Erro ao invocar prompt-engineer: {e}[/red]")
        return DEFAULT_MEETING_PROMPT


def _handle_user_prompt_workflow(user_prompt, prompt_engineer_available):
    """
    Cenário A: Usuário forneceu prompt → Melhorar AUTOMATICAMENTE → Confirmar.
    
    Returns:
        str: Prompt final a usar
    """
    console.print("\n[cyan]📝 Prompt fornecido pelo usuário[/cyan]")
    console.print(Panel(user_prompt[:300] + ("..." if len(user_prompt) > 300 else ""), 
                       title="Prompt original", border_style="dim"))
    
    if prompt_engineer_available:
        # Melhora AUTOMATICAMENTE (sem perguntar)
        console.print("\n[cyan]🔧 Melhorando prompt com prompt-engineer...[/cyan]")
        
        improved_prompt = invoke_prompt_engineer(
            f"melhore este prompt:\n\n{user_prompt}"
        )
        
        # Mostrar AMBAS versões
        console.print("\n[green]✨ Versão melhorada:[/green]")
        console.print(Panel(improved_prompt[:500] + ("..." if len(improved_prompt) > 500 else ""), 
                           title="Prompt otimizado", border_style="green"))
        
        console.print("\n[dim]📝 Versão original:[/dim]")
        console.print(Panel(user_prompt[:300] + ("..." if len(user_prompt) > 300 else ""), 
                           title="Seu prompt", border_style="dim"))
        
        # Pergunta qual usar
        confirm = Prompt.ask(
            "\n💡 Usar versão melhorada?",
            choices=["s", "n"],
            default="s"
        )
        
        return improved_prompt if confirm == "s" else user_prompt
    else:
        # prompt-engineer não disponível
        console.print("[yellow]⚠️  prompt-engineer skill não disponível[/yellow]")
        console.print("[dim]✅ Usando seu prompt original[/dim]")
        return user_prompt


def _suggest_transcript_type(transcript):
    """
    Analisa o transcript e sugere um tipo/formato de saída via prompt-engineer.
    
    Returns:
        str: Sugestão de tipo/formato
    """
    console.print("\n[cyan]🔍 Analisando transcript...[/cyan]")
    
    suggestion_meta_prompt = f"""
Analise este transcript ({len(transcript)} caracteres) e sugira:

1. Tipo de conteúdo (reunião, palestra, entrevista, etc.)
2. Formato de saída recomendado (ata formal, resumo executivo, notas estruturadas)
3. Framework ideal (RISEN, RODES, STAR, etc.)

Primeiras 1000 palavras do transcript:
{transcript[:4000]}

Responda em 2-3 linhas concisas.
"""
    
    return invoke_prompt_engineer(suggestion_meta_prompt)


def _generate_prompt_from_suggestion(suggested_type):
    """
    Gera um prompt completo e estruturado baseado na sugestão de tipo.
    
    Returns:
        str: Prompt gerado
    """
    console.print("\n[cyan]✨ Gerando prompt estruturado...[/cyan]")
    
    final_meta_prompt = f"""
Crie um prompt completo e estruturado (usando framework apropriado) para:

{suggested_type}

O prompt deve instruir uma IA a transformar o transcript em um documento
profissional e bem formatado em Markdown.
"""
    
    return invoke_prompt_engineer(final_meta_prompt)


def _handle_auto_generation_workflow(transcript, prompt_engineer_available):
    """
    Cenário B: Sem prompt → Sugerir tipo → Confirmar → Gerar → Confirmar.
    
    Returns:
        str: Prompt final a usar, ou None se usuário recusou processamento
    """
    console.print("\n[yellow]⚠️  Nenhum prompt fornecido.[/yellow]")
    
    if not prompt_engineer_available:
        console.print("[yellow]⚠️  prompt-engineer skill não encontrado[/yellow]")
        console.print("[dim]Usando template padrão...[/dim]")
        return DEFAULT_MEETING_PROMPT
    
    # PASSO 1: Perguntar se quer auto-gerar
    console.print("Posso analisar o transcript e sugerir um formato de resumo/ata?")
    
    generate = Prompt.ask(
        "\n💡 Gerar prompt automaticamente?",
        choices=["s", "n"],
        default="s"
    )
    
    if generate == "n":
        console.print("[dim]✅ Ok, gerando apenas transcript.md (sem ata)[/dim]")
        return None  # Sinaliza: não processar com LLM
    
    # PASSO 2: Analisar transcript e SUGERIR tipo
    suggested_type = _suggest_transcript_type(transcript)
    
    # PASSO 3: Mostrar sugestão e CONFIRMAR
    console.print("\n[green]💡 Sugestão de formato:[/green]")
    console.print(Panel(suggested_type, title="Análise do transcript", border_style="green"))
    
    confirm_type = Prompt.ask(
        "\n💡 Usar este formato?",
        choices=["s", "n"],
        default="s"
    )
    
    if confirm_type == "n":
        console.print("[dim]Usando template padrão...[/dim]")
        return DEFAULT_MEETING_PROMPT
    
    # PASSO 4: Gerar prompt completo baseado na sugestão
    generated_prompt = _generate_prompt_from_suggestion(suggested_type)
    
    # PASSO 5: Mostrar prompt gerado e CONFIRMAR
    console.print("\n[green]✅ Prompt gerado:[/green]")
    console.print(Panel(generated_prompt[:600] + ("..." if len(generated_prompt) > 600 else ""), 
                       title="Preview", border_style="green"))
    
    confirm_final = Prompt.ask(
        "\n💡 Usar este prompt?",
        choices=["s", "n"],
        default="s"
    )
    
    if confirm_final == "s":
        return generated_prompt
    else:
        console.print("[dim]Usando template padrão...[/dim]")
        return DEFAULT_MEETING_PROMPT


def handle_prompt_workflow(user_prompt, transcript):
    """
    Gerencia fluxo completo de prompts com prompt-engineer.
    
    Cenário A: Usuário forneceu prompt → Melhorar AUTOMATICAMENTE → Confirmar
    Cenário B: Sem prompt → Sugerir tipo → Confirmar → Gerar → Confirmar
    
    Returns:
        str: Prompt final a usar, ou None se usuário recusou processamento
    """
    prompt_engineer_available = os.path.exists(
        os.path.expanduser('~/.copilot/skills/prompt-engineer/SKILL.md')
    )
    
    if user_prompt:
        return _handle_user_prompt_workflow(user_prompt, prompt_engineer_available)
    else:
        return _handle_auto_generation_workflow(transcript, prompt_engineer_available)


def process_with_llm(transcript, prompt, cli_tool='claude', timeout=300):
    """
    Processa transcript com LLM usando prompt fornecido.
    
    Args:
        transcript: Texto transcrito
        prompt: Prompt instruindo como processar
        cli_tool: 'claude' ou 'gh-copilot'
        timeout: Timeout em segundos
    
    Returns:
        str: Ata/resumo processado
    """
    full_prompt = f"{prompt}\n\n---\n\nTranscrição:\n\n{transcript}"
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True
        ) as progress:
            progress.add_task(description=f"🤖 Processando com {cli_tool}...", total=None)
            
            if cli_tool == 'claude':
                result = subprocess.run(
                    ['claude', '-'],
                    input=full_prompt,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            elif cli_tool == 'gh-copilot':
                result = subprocess.run(
                    ['gh', 'copilot', 'suggest', '-t', 'shell', full_prompt],
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
            else:
                raise ValueError(f"CLI tool desconhecido: {cli_tool}")
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            console.print(f"[red]❌ Erro ao processar com {cli_tool}[/red]")
            console.print(f"[dim]{result.stderr[:200]}[/dim]")
            return None
            
    except subprocess.TimeoutExpired:
        console.print(f"[red]❌ Timeout após {timeout}s[/red]")
        return None
    except Exception as e:
        console.print(f"[red]❌ Erro: {e}[/red]")
        return None


def transcribe_audio(audio_file, model="base"):
    """
    Transcreve áudio usando Whisper com barra de progresso.
    
    Returns:
        dict: {language, duration, segments: [{start, end, text}]}
    """
    console.print(f"\n[cyan]🎙️  Transcrevendo áudio com {TRANSCRIBER}...[/cyan]")
    
    try:
        if TRANSCRIBER == "faster-whisper":
            model_obj = WhisperModel(model, device="cpu", compute_type="int8")
            segments, info = model_obj.transcribe(
                audio_file,
                language=None,
                vad_filter=True,
                word_timestamps=True
            )
            
            data = {
                "language": info.language,
                "language_probability": round(info.language_probability, 2),
                "duration": info.duration,
                "segments": []
            }
            
            # Converter generator em lista com progresso
            console.print("[dim]Processando segmentos...[/dim]")
            for segment in tqdm(segments, desc="Segmentos", unit="seg"):
                data["segments"].append({
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip()
                })
        
        else:  # whisper original
            import whisper
            model_obj = whisper.load_model(model)
            result = model_obj.transcribe(audio_file, word_timestamps=True)
            
            data = {
                "language": result["language"],
                "duration": result["segments"][-1]["end"] if result["segments"] else 0,
                "segments": result["segments"]
            }
        
        console.print(f"[green]✅ Transcrição completa! Idioma: {data['language'].upper()}[/green]")
        console.print(f"[dim]   {len(data['segments'])} segmentos processados[/dim]")
        
        return data
        
    except Exception as e:
        console.print(f"[red]❌ Erro na transcrição: {