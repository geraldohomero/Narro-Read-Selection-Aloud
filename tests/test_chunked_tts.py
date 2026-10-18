"""Testes unitários para geração progressiva de TTS em chunks e streaming gapless no mpv.
"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch, call

from narro_rsa.text_formatter import split_text_into_chunks
from narro_rsa.tts_engine import (
    EngineType,
    GenerationResult,
    TTSRequest,
    cleanup_chunk_files,
    generate_audio,
    get_chunk_audio_path,
)
from narro_rsa.mpv_control import (
    append_to_mpv_playlist,
    play_chunked_tts,
)


class TestSplitTextIntoChunks(unittest.TestCase):
    def test_split_text_into_chunks_empty(self):
        self.assertEqual(split_text_into_chunks(""), [])
        self.assertEqual(split_text_into_chunks("   \n\t  "), [])

    def test_split_text_into_chunks_short_text(self):
        text = "Este é um texto curto para teste de síntese de voz."
        chunks = split_text_into_chunks(text)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0], text)

    def test_split_text_into_chunks_multisentence(self):
        # Cria múltiplas frases totalizando ~1000 caracteres
        sentence_a = "Primeira frase curta de introdução."
        sentence_b = "Segunda frase com detalhes importantes sobre o funcionamento do sistema neural."
        sentence_c = "Terceira frase trazendo ainda mais contexto para garantir que o tamanho ultrapasse o primeiro limite."
        sentence_d = "Quarta frase longa que descreve a arquitetura de processamento em lote e como as frases são divididas com base na pontuação terminadora."
        sentence_e = "Quinta frase final que conclui o raciocínio e fecha o teste de divisão em múltiplos chunks para reprodução progressiva."
        
        full_text = f"{sentence_a} {sentence_b} {sentence_c} {sentence_d} {sentence_e}"
        chunks = split_text_into_chunks(full_text, first_chunk_max_chars=220, next_chunk_max_chars=600)
        
        self.assertGreater(len(chunks), 1)
        # Chunk 0 deve ter <= 220 caracteres
        self.assertLessEqual(len(chunks[0]), 220)
        # Chunks seguintes devem ter <= 600 caracteres
        for i, chunk in enumerate(chunks[1:], start=1):
            self.assertLessEqual(len(chunk), 600, f"Chunk {i} ultrapassou 600 chars: {len(chunk)}")
            self.assertTrue(len(chunk) > 0)

        # Frases não devem ser truncadas no meio se couberem
        self.assertTrue(chunks[0].endswith("."))

    def test_split_text_into_chunks_long_unpunctuated(self):
        # Texto sem pontuação longa composto por palavras de 5 letras
        words = [f"palavra{i}" for i in range(120)]
        unpunctuated_text = " ".join(words)
        
        chunks = split_text_into_chunks(unpunctuated_text, first_chunk_max_chars=220, next_chunk_max_chars=600)
        self.assertGreater(len(chunks), 1)
        self.assertLessEqual(len(chunks[0]), 220)
        
        # Nenhuma palavra deve ser cortada ao meio
        for chunk in chunks:
            chunk_words = chunk.split()
            for w in chunk_words:
                self.assertTrue(w.startswith("palavra"), f"Palavra cortada: {w}")

        # Reunião das palavras deve bater com a lista original
        reconstructed_words = []
        for chunk in chunks:
            reconstructed_words.extend(chunk.split())
        self.assertEqual(reconstructed_words, words)


class TestTTSEngineChunking(unittest.TestCase):
    def test_get_chunk_audio_path_and_cleanup(self):
        piper_path = get_chunk_audio_path(0, EngineType.PIPER)
        edge_path = get_chunk_audio_path(1, EngineType.EDGE_TTS)

        self.assertTrue(piper_path.endswith("narro-chunk-0.wav"))
        self.assertTrue(edge_path.endswith("narro-chunk-1.mp3"))

        # Cria arquivos fictícios para testar o cleanup
        try:
            with open(piper_path, "w", encoding="utf-8") as f:
                f.write("dummy")
            with open(edge_path, "w", encoding="utf-8") as f:
                f.write("dummy")
            self.assertTrue(os.path.exists(piper_path))
            self.assertTrue(os.path.exists(edge_path))

            cleanup_chunk_files()
            self.assertFalse(os.path.exists(piper_path))
            self.assertFalse(os.path.exists(edge_path))
        finally:
            cleanup_chunk_files()

    @patch("narro_rsa.tts_engine.run_command")
    @patch("os.path.exists")
    def test_generate_audio_with_output_path(self, mock_exists, mock_run):
        mock_exists.return_value = True
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_run.return_value = mock_proc

        custom_output = "/tmp/narro-test-custom.wav"
        req = TTSRequest(text="Texto de teste", voice="pt_BR-cadu-medium", engine=EngineType.PIPER, speed=1.0)
        
        res = generate_audio(req, output_path=custom_output, preformatted=True)
        self.assertTrue(res.success)
        self.assertEqual(res.audio_path, custom_output)
        
        # Verifica se o comando usou custom_output
        call_args = mock_run.call_args[0][0]
        self.assertIn("--output_file", call_args)
        out_idx = call_args.index("--output_file")
        self.assertEqual(call_args[out_idx + 1], custom_output)


class TestMpvControlChunking(unittest.TestCase):
    @patch("narro_rsa.mpv_control.send_mpv_command")
    def test_append_to_mpv_playlist(self, mock_send):
        mock_send.return_value = {"error": "success"}
        ok = append_to_mpv_playlist("/tmp/narro-chunk-1.wav")
        self.assertTrue(ok)
        mock_send.assert_called_once_with(["loadfile", "/tmp/narro-chunk-1.wav", "append-play"], timeout=2.0)

    @patch("narro_rsa.mpv_control.cleanup_chunk_files")
    @patch("narro_rsa.mpv_control.generate_audio")
    @patch("narro_rsa.mpv_control.popen_command")
    @patch("narro_rsa.mpv_control.split_text_into_chunks")
    def test_play_chunked_tts_single_chunk(self, mock_split, mock_popen, mock_gen, mock_clean):
        mock_split.return_value = ["Frase única."]
        mock_gen.return_value = GenerationResult(success=True, audio_path="/tmp/narro-chunk-0.wav", engine_name="piper", error_message="")
        mock_proc = MagicMock()
        mock_popen.return_value = mock_proc

        first_ready_cb = MagicMock()
        req = TTSRequest(text="Frase única.", voice="v1", engine=EngineType.PIPER, speed=1.0)

        proc, thread = play_chunked_tts(req, on_first_chunk_ready=first_ready_cb)

        self.assertEqual(proc, mock_proc)
        self.assertIsNone(thread)
        first_ready_cb.assert_called_once_with(mock_proc)
        mock_clean.assert_called_once()
        mock_popen.assert_called_once()
        # Para chunk único, --idle=yes NÃO deve ser passado
        popen_args = mock_popen.call_args[0][0]
        self.assertNotIn("--idle=yes", popen_args)

    @patch("narro_rsa.mpv_control.send_mpv_command")
    @patch("narro_rsa.mpv_control.append_to_mpv_playlist")
    @patch("narro_rsa.mpv_control.cleanup_chunk_files")
    @patch("narro_rsa.mpv_control.generate_audio")
    @patch("narro_rsa.mpv_control.popen_command")
    @patch("narro_rsa.mpv_control.split_text_into_chunks")
    def test_play_chunked_tts_multiple_chunks_appends_playlist(
        self, mock_split, mock_popen, mock_gen, mock_clean, mock_append, mock_send
    ):
        mock_split.return_value = ["Chunk 0.", "Chunk 1.", "Chunk 2."]
        mock_gen.side_effect = lambda req, output_path=None, preformatted=False: GenerationResult(
            success=True, audio_path=output_path or "/tmp/audio.wav", engine_name="piper", error_message=""
        )
        mock_send.return_value = {"error": "success"}
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        req = TTSRequest(text="Texto longo...", voice="v1", engine=EngineType.PIPER, speed=1.0)
        proc, thread = play_chunked_tts(req)

        self.assertEqual(proc, mock_proc)
        self.assertIsNotNone(thread)

        # Deve iniciar com --idle=yes quando há múltiplos chunks
        popen_args = mock_popen.call_args[0][0]
        self.assertIn("--idle=yes", popen_args)

        # Aguarda thread concluir a geração dos chunks subsequentes
        thread.join(timeout=2.0)

        self.assertEqual(mock_append.call_count, 2)
        # Chunk 1 e 2 devem ter sido anexados
        appended_files = [c[0][0] for c in mock_append.call_args_list]
        self.assertTrue(any("narro-chunk-1" in f for f in appended_files))
        self.assertTrue(any("narro-chunk-2" in f for f in appended_files))

        # Ao terminar o último chunk, deve ter enviado set_property idle no ao mpv
        idle_no_calls = [c for c in mock_send.call_args_list if c[0][0] == ["set_property", "idle", "no"]]
        self.assertTrue(len(idle_no_calls) >= 1)

    @patch("narro_rsa.mpv_control.send_mpv_command")
    @patch("narro_rsa.mpv_control.append_to_mpv_playlist")
    @patch("narro_rsa.mpv_control.cleanup_chunk_files")
    @patch("narro_rsa.mpv_control.generate_audio")
    @patch("narro_rsa.mpv_control.popen_command")
    @patch("narro_rsa.mpv_control.split_text_into_chunks")
    def test_play_chunked_tts_aborts_when_mpv_stops(
        self, mock_split, mock_popen, mock_gen, mock_clean, mock_append, mock_send
    ):
        mock_split.return_value = ["Chunk 0.", "Chunk 1.", "Chunk 2.", "Chunk 3."]
        mock_gen.side_effect = lambda req, output_path=None, preformatted=False: GenerationResult(
            success=True, audio_path=output_path or "/tmp/audio.wav", engine_name="piper", error_message=""
        )
        mock_proc = MagicMock()
        # MPV morre antes de gerar o chunk 1
        mock_proc.poll.return_value = 0
        mock_popen.return_value = mock_proc

        req = TTSRequest(text="Texto longo...", voice="v1", engine=EngineType.PIPER, speed=1.0)
        proc, thread = play_chunked_tts(req)

        thread.join(timeout=2.0)

        # Como mpv já havia parado, nenhum chunk subsequente deve ter sido anexado
        mock_append.assert_not_called()

    @patch("narro_rsa.mpv_control.send_mpv_command")
    @patch("narro_rsa.mpv_control.append_to_mpv_playlist")
    @patch("narro_rsa.mpv_control.cleanup_chunk_files")
    @patch("narro_rsa.mpv_control.generate_audio")
    @patch("narro_rsa.mpv_control.popen_command")
    @patch("narro_rsa.mpv_control.split_text_into_chunks")
    def test_play_chunked_tts_error_in_subsequent_chunk_disables_idle(
        self, mock_split, mock_popen, mock_gen, mock_clean, mock_append, mock_send
    ):
        mock_split.return_value = ["Chunk 0.", "Chunk 1.", "Chunk 2."]

        def _fake_gen(req, output_path=None, preformatted=False):
            if "Chunk 1." in req.text:
                return GenerationResult(success=False, audio_path="", engine_name="piper", error_message="Network error")
            return GenerationResult(success=True, audio_path=output_path or "/tmp/dummy.wav", engine_name="piper", error_message="")

        mock_gen.side_effect = _fake_gen
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        err_cb = MagicMock()
        req = TTSRequest(text="Texto longo...", voice="v1", engine=EngineType.PIPER, speed=1.0)
        proc, thread = play_chunked_tts(req, on_error=err_cb)

        thread.join(timeout=2.0)

        err_cb.assert_called_once_with("Network error")
        # Ao falhar, deve instruir o mpv a desativar idle para não travar
        idle_no_calls = [c for c in mock_send.call_args_list if c[0][0] == ["set_property", "idle", "no"]]
        self.assertTrue(len(idle_no_calls) >= 1)


if __name__ == "__main__":
    unittest.main()
