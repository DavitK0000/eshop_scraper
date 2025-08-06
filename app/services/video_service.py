"""
Video Processing Service

This module provides video processing capabilities including:
- Downloading videos from URLs
- Merging multiple videos
- Adding audio and subtitles
- Extracting thumbnails
- Converting to base64 format
"""

import asyncio
import base64
import os
import tempfile
import uuid
import subprocess
from datetime import datetime
from typing import Dict, Any, Optional, List
import httpx

from app.models import TaskStatus, VideoProcessResponse
from app.logging_config import get_logger

logger = get_logger(__name__)


class VideoProcessingService:
    """Service for processing videos with audio and subtitle support."""
    
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
    # ============================================================================
    # Public API Methods
    # ============================================================================
    
    async def process_video(
        self,
        video_urls: List[str],
        audio_data: str,
        subtitle_text: Optional[str] = None,
        output_resolution: str = "1920x1080",
        watermark: bool = False
    ) -> VideoProcessResponse:
        """
        Process video by merging multiple videos, adding audio, and embedding subtitles.
        
        Args:
            video_urls: List of video URLs to download and merge
            audio_data: Base64 encoded audio data
            subtitle_text: Optional SRT subtitle text
            output_resolution: Output video resolution (default: 1920x1080)
            
        Returns:
            VideoProcessResponse with task ID and status
        """
        task_id = str(uuid.uuid4())
        
        # Create task entry
        self._create_task(task_id)
        
        # Start processing in background
        asyncio.create_task(self._process_video_task(
            task_id, video_urls, audio_data, subtitle_text, output_resolution, watermark
        ))
        
        return VideoProcessResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status by task ID."""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tasks."""
        return self.tasks.copy()
    
    # ============================================================================
    # Main Processing Pipeline
    # ============================================================================
    
    async def _process_video_task(
        self,
        task_id: str,
        video_urls: List[str],
        audio_data: str,
        subtitle_text: Optional[str],
        output_resolution: str,
        watermark: bool
    ):
        """Main video processing pipeline."""
        try:
            self._update_task_status(task_id, TaskStatus.RUNNING, "Starting video processing")
            
            with tempfile.TemporaryDirectory() as temp_dir:
                # Step 1: Download videos
                self._update_task_status(task_id, TaskStatus.RUNNING, "Downloading videos")
                video_files = await self._download_videos(video_urls, temp_dir)
                
                # Step 2: Save audio data
                self._update_task_status(task_id, TaskStatus.RUNNING, "Processing audio")
                audio_file = self._save_audio_data(audio_data, temp_dir)
                
                # Step 3: Create subtitle file (if provided)
                subtitle_file = None
                if subtitle_text:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Creating subtitles")
                    subtitle_file = self._create_subtitle_file(subtitle_text, temp_dir)
                
                # Step 4: Merge videos
                self._update_task_status(task_id, TaskStatus.RUNNING, "Merging videos")
                merged_video = self._merge_videos(video_files, temp_dir, output_resolution)
                
                # Step 5: Add audio, subtitles, and watermark
                if subtitle_text and watermark:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio, subtitles, and watermark")
                elif subtitle_text:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio and subtitles")
                elif watermark:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio and watermark")
                else:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio")
                final_video = self._add_audio_subtitles_and_watermark_to_video(
                    merged_video, audio_file, subtitle_file, watermark, temp_dir, output_resolution
                )
                
                # Step 6: Extract thumbnail and encode results
                self._update_task_status(task_id, TaskStatus.RUNNING, "Extracting thumbnail")
                thumbnail_base64 = self._extract_and_encode_thumbnail(merged_video, temp_dir)
                self._update_task_status(task_id, TaskStatus.RUNNING, "Encoding final video")
                video_base64 = self._encode_video_to_base64(final_video)
                
                # Step 7: Update task with success
                self._complete_task_success(task_id, video_base64, thumbnail_base64)
                
        except Exception as e:
            logger.error(f"Error processing video task {task_id}: {e}", exc_info=True)
            self._complete_task_failure(task_id, str(e))
    
    # ============================================================================
    # Video Download Methods
    # ============================================================================
    
    async def _download_videos(self, video_urls: List[str], temp_dir: str) -> List[str]:
        """Download videos from URLs."""
        
        # Remove duplicate URLs
        unique_urls = self._remove_duplicates_preserve_order(video_urls)
        if len(unique_urls) != len(video_urls):
            logger.warning(f"Removed {len(video_urls) - len(unique_urls)} duplicate URLs")
        
        logger.info(f"Downloading {len(unique_urls)} videos from URLs")
        
        video_files = []
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(unique_urls):
                video_file = await self._download_single_video(client, url, temp_dir, i)
                video_files.append(video_file)
        
        logger.info(f"Successfully downloaded {len(video_files)} videos")
        return video_files
    
    async def _download_single_video(
        self, 
        client: httpx.AsyncClient, 
        url: str, 
        temp_dir: str, 
        index: int
    ) -> str:
        """Download a single video from URL."""
        try:
            logger.info(f"Downloading video {index+1}: {url}")
            response = await client.get(url)
            response.raise_for_status()
            
            video_file = os.path.join(temp_dir, f"video_{index}.mp4")
            with open(video_file, 'wb') as f:
                f.write(response.content)
            
            logger.info(f"Downloaded: {os.path.basename(video_file)} ({len(response.content)} bytes)")
            return video_file
            
        except Exception as e:
            raise Exception(f"Failed to download video {url}: {str(e)}")
    
    # ============================================================================
    # Audio Processing Methods
    # ============================================================================
    
    def _save_audio_data(self, audio_data: str, temp_dir: str) -> str:
        """Save base64 audio data to file."""
        
        try:
            audio_bytes = base64.b64decode(audio_data)
            audio_file = os.path.join(temp_dir, "audio.mp3")
            with open(audio_file, 'wb') as f:
                f.write(audio_bytes)
            return audio_file
        except Exception as e:
            raise Exception(f"Failed to save audio data: {str(e)}")
    
    # ============================================================================
    # Subtitle Processing Methods
    # ============================================================================
    
    def _create_subtitle_file(self, subtitle_srt: str, temp_dir: str) -> str:
        """Create subtitle file and convert to ASS format if possible."""
        
        subtitle_file = os.path.join(temp_dir, "subtitles.srt")
        ass_file = os.path.join(temp_dir, "subtitles.ass")
        
        # Write SRT content
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write(subtitle_srt)
        
        # Validate SRT format
        if not self._is_valid_srt_format(subtitle_srt):
            logger.warning("SRT format appears invalid, using as-is")
            return subtitle_file
        
        # Try to convert to ASS format
        if self._convert_srt_to_ass(subtitle_file, ass_file, temp_dir):
            return ass_file
        
        return subtitle_file
    
    def _is_valid_srt_format(self, subtitle_srt: str) -> bool:
        """Check if SRT content has valid format."""
        lines = subtitle_srt.strip().split('\n')
        return len(lines) >= 4 and lines[0].isdigit()
    
    def _convert_srt_to_ass(self, srt_file: str, ass_file: str, temp_dir: str) -> bool:
        """Convert SRT file to ASS format using FFmpeg."""
        cmd = ['ffmpeg', '-y', '-i', srt_file, ass_file]
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
        
        if result.returncode != 0:
            logger.warning(f"Failed to convert SRT to ASS: {result.stderr}")
            return False
        
        return os.path.exists(ass_file) and os.path.getsize(ass_file) > 0
    
    # ============================================================================
    # Video Merging Methods
    # ============================================================================
    
    def _merge_videos(self, video_files: List[str], temp_dir: str, output_resolution: str) -> str:
        """Merge multiple videos using FFmpeg."""
        
        if len(video_files) == 1:
            return video_files[0]
        
        # Remove duplicate video files
        unique_video_files = self._remove_duplicates_preserve_order(video_files)
        if len(unique_video_files) != len(video_files):
            logger.warning(f"Removed {len(video_files) - len(unique_video_files)} duplicate video files")
        
        # Verify all files exist
        self._verify_video_files_exist(unique_video_files)
        
        # Log video files being merged
        self._log_video_files_for_merging(unique_video_files)
        
        # Try primary merging method
        try:
            return self._merge_videos_with_concat_demuxer(unique_video_files, temp_dir)
        except Exception as e:
            logger.warning(f"Primary merge method failed: {e}")
            return self._merge_videos_with_filter_complex(unique_video_files, temp_dir)
    
    def _merge_videos_with_concat_demuxer(self, video_files: List[str], temp_dir: str) -> str:
        """Merge videos using FFmpeg concat demuxer."""
        file_list = self._create_ffmpeg_file_list(video_files, temp_dir)
        merged_video = os.path.join(temp_dir, "merged.mp4")
        
        cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', file_list,
            '-c', 'copy',
            merged_video
        ]
        
        self._run_ffmpeg_command(cmd, "concat demuxer")
        logger.info(f"Successfully merged videos using concat demuxer: {merged_video}")
        return merged_video
    
    def _merge_videos_with_filter_complex(self, video_files: List[str], temp_dir: str) -> str:
        """Merge videos using FFmpeg filter_complex."""
        merged_video = os.path.join(temp_dir, "merged_alt.mp4")
        
        inputs = []
        filter_parts = []
        
        for i, video_file in enumerate(video_files):
            inputs.extend(['-i', video_file])
            filter_parts.append(f'[{i}:v:0][{i}:a:0]')
        
        filter_complex = ''.join(filter_parts) + f'concat=n={len(video_files)}:v=1:a=1[outv][outa]'
        
        cmd = [
            'ffmpeg', '-y'
        ] + inputs + [
            '-filter_complex', filter_complex,
            '-map', '[outv]',
            '-map', '[outa]',
            '-c:v', 'copy',
            '-c:a', 'copy',
            merged_video
        ]
        
        self._run_ffmpeg_command(cmd, "filter_complex")
        logger.info(f"Successfully merged videos using filter_complex: {merged_video}")
        return merged_video
    
    def _create_ffmpeg_file_list(self, video_files: List[str], temp_dir: str) -> str:
        """Create FFmpeg file list for concat demuxer."""
        file_list = os.path.join(temp_dir, "file_list.txt")
        with open(file_list, 'w') as f:
            for video_file in video_files:
                f.write(f"file '{video_file}'\n")
        
        # Log file list content for debugging
        with open(file_list, 'r') as f:
            logger.info(f"File list content:\n{f.read()}")
        
        return file_list
    
    # ============================================================================
    # Audio, Subtitle, and Watermark Addition Methods
    # ============================================================================
    
    def _add_audio_subtitles_and_watermark_to_video(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: Optional[str],
        watermark: bool,
        temp_dir: str,
        output_resolution: str
    ) -> str:
        """Add audio, subtitles, and watermark to video."""
        if subtitle_file and watermark:
            return self._add_audio_subtitles_and_watermark(video_file, audio_file, subtitle_file, temp_dir)
        elif subtitle_file:
            return self._add_audio_and_subtitles(video_file, audio_file, subtitle_file, temp_dir)
        elif watermark:
            return self._add_audio_and_watermark(video_file, audio_file, temp_dir)
        else:
            return self._add_audio_only(video_file, audio_file, temp_dir)
    
    def _add_audio_and_subtitles_to_video(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: Optional[str],
        temp_dir: str,
        output_resolution: str
    ) -> str:
        """Add audio and subtitles to video."""
        if subtitle_file:
            return self._add_audio_and_subtitles(video_file, audio_file, subtitle_file, temp_dir)
        else:
            return self._add_audio_only(video_file, audio_file, temp_dir)
    
    def _add_audio_and_subtitles(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        temp_dir: str
    ) -> str:
        """Add audio and burn subtitles into video."""
        final_video = os.path.join(temp_dir, "final.mp4")
        subtitle_filename = os.path.basename(subtitle_file)
        
        # Try multiple approaches for subtitle addition
        methods = [
            self._try_ass_subtitle_only,
            self._try_srt_subtitle_only,
            self._try_audio_only
        ]
        
        for method in methods:
            try:
                result = method(video_file, audio_file, subtitle_file, final_video, temp_dir)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        # If all methods fail, fall back to audio only
        logger.warning("All subtitle methods failed, using audio only")
        return self._add_audio_only(video_file, audio_file, temp_dir)
    
    def _try_ass_subtitle_only(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try ASS subtitle only (no watermark)."""
        subtitle_filename = os.path.basename(subtitle_file)
        if not subtitle_filename.endswith('.ass'):
            return None
            
        logger.info("Trying ASS subtitle only...")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', f'ass={subtitle_filename}',
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "ASS subtitle only", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"ASS subtitle only failed - file not created: {final_video}")
            return None
    
    def _try_srt_subtitle_only(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try SRT subtitle only (no watermark)."""
        subtitle_filename = os.path.basename(subtitle_file)
        if not subtitle_filename.endswith('.srt'):
            return None
            
        logger.info("Trying SRT subtitle only...")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', f"subtitles='{subtitle_filename}'",
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "SRT subtitle only", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"SRT subtitle only failed - file not created: {final_video}")
            return None
    
    def _add_audio_and_watermark(
        self,
        video_file: str,
        audio_file: str,
        temp_dir: str
    ) -> str:
        """Add audio and watermark to video."""
        final_video = os.path.join(temp_dir, "final.mp4")
        
        # Create watermark filter with "PromoNexAI" text using Windows default font
        watermark_filter = (
            "drawtext=text='PromoNexAI':fontcolor=white@0.9:fontsize=120:"
            "fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', watermark_filter,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "audio and watermark addition", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            raise Exception(f"Audio and watermark addition failed - file not created: {final_video}")
    
    def _add_audio_subtitles_and_watermark(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        temp_dir: str
    ) -> str:
        """Add audio, subtitles, and watermark to video."""
        final_video = os.path.join(temp_dir, "final.mp4")
        subtitle_filename = os.path.basename(subtitle_file)
        
        # Try multiple approaches for subtitle and watermark addition
        methods = [
            self._try_ass_subtitle_with_watermark,
            self._try_srt_subtitle_with_watermark,
            self._try_watermark_only_with_audio,
            self._try_simple_watermark_with_audio,
            self._try_audio_only
        ]
        
        for method in methods:
            try:
                result = method(video_file, audio_file, subtitle_file, final_video, temp_dir)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Method {method.__name__} failed: {e}")
                continue
        
        # If all methods fail, fall back to audio only
        logger.warning("All subtitle and watermark methods failed, using audio only")
        return self._add_audio_only(video_file, audio_file, temp_dir)
    
    def _try_ass_subtitle_with_watermark(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try ASS subtitle with watermark."""
        subtitle_filename = os.path.basename(subtitle_file)
        if not subtitle_filename.endswith('.ass'):
            return None
            
        logger.info("Trying ASS subtitle with watermark...")
        
        combined_filter = (
            f"ass={subtitle_filename},"
            "drawtext=text='PromoNexAI':fontcolor=white@0.9:fontsize=120:"
            "fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', combined_filter,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "ASS subtitle with watermark", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"ASS subtitle with watermark failed - file not created: {final_video}")
            return None
    
    def _try_srt_subtitle_with_watermark(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try SRT subtitle with watermark."""
        subtitle_filename = os.path.basename(subtitle_file)
        if not subtitle_filename.endswith('.srt'):
            return None
            
        logger.info("Trying SRT subtitle with watermark...")
        
        combined_filter = (
            f"subtitles='{subtitle_filename}',"
            "drawtext=text='PromoNexAI':fontcolor=white@0.9:fontsize=120:"
            "fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', combined_filter,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "SRT subtitle with watermark", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"SRT subtitle with watermark failed - file not created: {final_video}")
            return None
    
    def _try_watermark_only_with_audio(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try watermark only with audio (no subtitles)."""
        logger.info("Trying watermark only with audio...")
        
        watermark_filter = (
            "drawtext=text='PromoNexAI':fontcolor=white@0.9:fontsize=120:"
            "fontfile='C\\:/Windows/Fonts/arial.ttf':"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', watermark_filter,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "watermark only with audio", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"Watermark only with audio failed - file not created: {final_video}")
            return None
    
    def _try_simple_watermark_with_audio(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try simple watermark with audio (no subtitles, basic text)."""
        logger.info("Trying simple watermark with audio...")
        
        # Use a simpler watermark without complex font settings
        simple_watermark_filter = (
            "drawtext=text='PromoNexAI':fontcolor=white@0.9:fontsize=120:"
            "x=(w-text_w)/2:y=(h-text_h)/2"
        )
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-vf', simple_watermark_filter,
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-shortest',
            '-pix_fmt', 'yuv420p',
            '-crf', '23',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "simple watermark with audio", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            logger.error(f"Simple watermark with audio failed - file not created: {final_video}")
            return None
    
    def _try_audio_only(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        final_video: str,
        temp_dir: str
    ) -> Optional[str]:
        """Try audio only (no subtitles, no watermark)."""
        logger.info("Trying audio only...")
        return self._add_audio_only(video_file, audio_file, temp_dir)
    
    def _add_audio_only(self, video_file: str, audio_file: str, temp_dir: str) -> str:
        """Add audio to video without subtitles."""
        final_video = os.path.join(temp_dir, "final.mp4")
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-i', os.path.basename(audio_file),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            os.path.basename(final_video)
        ]
        
        self._run_ffmpeg_command(cmd, "audio addition", cwd=temp_dir)
        
        # Verify the file was created
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            return final_video
        else:
            raise Exception(f"Audio addition failed - file not created: {final_video}")
    
    # ============================================================================
    # Thumbnail and Encoding Methods
    # ============================================================================
    
    def _extract_and_encode_thumbnail(self, video_file: str, temp_dir: str) -> str:
        """Extract thumbnail from video and encode to base64."""
        
        thumbnail_file = self._extract_thumbnail(video_file, temp_dir)
        return self._encode_thumbnail_to_base64(thumbnail_file)
    
    def _extract_thumbnail(self, video_file: str, temp_dir: str) -> str:
        """Extract thumbnail from video using FFmpeg."""
        thumbnail_file = os.path.join(temp_dir, "thumbnail.jpg")
        
        # Try extracting at 1 second first
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),
            '-ss', '00:00:01',
            '-vframes', '1',
            '-q:v', '2',
            '-f', 'image2',
            os.path.basename(thumbnail_file)
        ]
        
        try:
            self._run_ffmpeg_command(cmd, "thumbnail extraction at 1s", cwd=temp_dir)
        except Exception:
            # Try extracting at 0 seconds if 1 second fails
            cmd[3] = '00:00:00'  # Change seek time to 0 seconds
            self._run_ffmpeg_command(cmd, "thumbnail extraction at 0s", cwd=temp_dir)
        
        # Verify the thumbnail was created
        if not os.path.exists(thumbnail_file) or os.path.getsize(thumbnail_file) == 0:
            raise Exception(f"Thumbnail extraction failed - file not created: {thumbnail_file}")
        
        return thumbnail_file
    
    def _encode_video_to_base64(self, video_file: str) -> str:
        """Encode video file to base64."""
        
        try:
            with open(video_file, 'rb') as f:
                video_bytes = f.read()
            return base64.b64encode(video_bytes).decode('utf-8')
        except Exception as e:
            raise Exception(f"Failed to encode video to base64: {str(e)}")
    
    def _encode_thumbnail_to_base64(self, thumbnail_file: str) -> str:
        """Encode thumbnail image to base64 string."""
        try:
            with open(thumbnail_file, 'rb') as f:
                thumbnail_bytes = f.read()
            return base64.b64encode(thumbnail_bytes).decode('utf-8')
        except Exception as e:
            raise Exception(f"Failed to encode thumbnail to base64: {str(e)}")
    
    # ============================================================================
    # Utility Methods
    # ============================================================================
    
    def _remove_duplicates_preserve_order(self, items: List[str]) -> List[str]:
        """Remove duplicates while preserving order."""
        return list(dict.fromkeys(items))
    
    def _verify_video_files_exist(self, video_files: List[str]):
        """Verify all video files exist."""
        for video_file in video_files:
            if not os.path.exists(video_file):
                raise Exception(f"Video file not found: {video_file}")
    
    def _log_video_files_for_merging(self, video_files: List[str]):
        """Log video files being merged."""
        logger.info(f"Merging {len(video_files)} videos:")
        for i, video_file in enumerate(video_files):
            logger.info(f"  {i+1}. {os.path.basename(video_file)}")
    
    def _run_ffmpeg_command(self, cmd: List[str], operation: str, cwd: Optional[str] = None):
        """Run FFmpeg command with error handling."""
        logger.info(f"Running FFmpeg {operation}: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        
        # Always check if the output file was created, regardless of return code
        output_file = None
        for arg in cmd:
            if arg.endswith('.mp4') and not arg.startswith('-'):
                output_file = arg
                break
        
        if output_file and cwd:
            output_file = os.path.join(cwd, output_file)
        
        file_created = output_file and os.path.exists(output_file) and os.path.getsize(output_file) > 0
        
        if result.returncode != 0:
            # Check if it's just a font configuration warning
            if "Fontconfig error" in result.stderr and "Cannot load default config file" in result.stderr:
                if file_created:
                    logger.warning(f"Font configuration warning in {operation}, but file was created successfully")
                    return
                else:
                    logger.error(f"Font configuration warning and file not created: {output_file}")
                    logger.error(f"FFmpeg stderr: {result.stderr}")
                    raise Exception(f"FFmpeg {operation} failed despite font warning: {result.stderr}")
            
            logger.error(f"FFmpeg {operation} failed: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            raise Exception(f"FFmpeg {operation} failed: {result.stderr}")
        elif not file_created:
            logger.error(f"FFmpeg {operation} returned success but file not created: {output_file}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            raise Exception(f"FFmpeg {operation} succeeded but file not created: {output_file}")
    
    # ============================================================================
    # Task Management Methods
    # ============================================================================
    
    def _create_task(self, task_id: str):
        """Create a new task entry."""
        self.tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'message': 'Task created'
        }
    
    def _update_task_status(self, task_id: str, status: TaskStatus, message: str):
        """Update task status."""
        if task_id in self.tasks:
            self.tasks[task_id].update({
                'status': status,
                'message': message,
                'updated_at': datetime.now()
            })
    
    def _complete_task_success(self, task_id: str, video_base64: str, thumbnail_base64: str):
        """Complete task with success."""
        self.tasks[task_id].update({
            'status': TaskStatus.COMPLETED,
            'video_data': video_base64,
            'thumbnail_data': thumbnail_base64,
            'completed_at': datetime.now(),
            'updated_at': datetime.now(),
            'message': 'Video processing completed successfully'
        })
    
    def _complete_task_failure(self, task_id: str, error_message: str):
        """Complete task with failure."""
        self.tasks[task_id].update({
            'status': TaskStatus.FAILED,
            'error': error_message,
            'updated_at': datetime.now(),
            'message': f'Video processing failed: {error_message}'
        })


# Global instance
video_service = VideoProcessingService() 