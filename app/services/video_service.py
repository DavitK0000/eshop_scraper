import asyncio
import base64
import os
import tempfile
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import subprocess
import json

from app.models import TaskStatus, VideoProcessResponse

logger = logging.getLogger(__name__)


class VideoProcessingService:
    def __init__(self):
        self.tasks: Dict[str, Dict[str, Any]] = {}
    
    async def process_video(
        self,
        video_urls: list[str],
        audio_data: str,
        subtitle_text: Optional[str] = None,
        output_resolution: str = "1920x1080"
    ) -> VideoProcessResponse:
        """
        Process video by merging multiple videos, adding audio, and embedding subtitles
        """
        task_id = str(uuid.uuid4())
        
        # Create task entry
        self.tasks[task_id] = {
            'status': TaskStatus.PENDING,
            'created_at': datetime.now(),
            'updated_at': datetime.now(),
            'message': 'Task created'
        }
        
        # Start processing in background
        asyncio.create_task(self._process_video_task(
            task_id, video_urls, audio_data, subtitle_text, output_resolution
        ))
        
        return VideoProcessResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now()
        )
    
    async def _process_video_task(
        self,
        task_id: str,
        video_urls: list[str],
        audio_data: str,
        subtitle_text: Optional[str],
        output_resolution: str
    ):
        """Background task to process the video"""
        try:
            self._update_task_status(task_id, TaskStatus.RUNNING, "Starting video processing")
            
            # Create temporary directory for processing
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download videos
                self._update_task_status(task_id, TaskStatus.RUNNING, "Downloading videos")
                video_files = await self._download_videos(video_urls, temp_dir)
                
                # Save audio data
                self._update_task_status(task_id, TaskStatus.RUNNING, "Processing audio")
                audio_file = self._save_audio_data(audio_data, temp_dir)
                
                # Create subtitle file (if provided)
                subtitle_file = None
                if subtitle_text:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Creating subtitles")
                    subtitle_file = self._create_subtitle_file(subtitle_text, temp_dir)
                
                # Merge videos
                self._update_task_status(task_id, TaskStatus.RUNNING, "Merging videos")
                merged_video = self._merge_videos(video_files, temp_dir, output_resolution)
                
                # Add audio and subtitles (if provided)
                if subtitle_text:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio and subtitles")
                    final_video = self._add_audio_and_subtitles(
                        merged_video, audio_file, subtitle_file, temp_dir, output_resolution
                    )
                else:
                    self._update_task_status(task_id, TaskStatus.RUNNING, "Adding audio")
                    final_video = self._add_audio_only(
                        merged_video, audio_file, temp_dir, output_resolution
                    )
                
                # Convert to base64
                self._update_task_status(task_id, TaskStatus.RUNNING, "Encoding final video")
                video_base64 = self._encode_video_to_base64(final_video)
                
                # Update task with success
                self.tasks[task_id].update({
                    'status': TaskStatus.COMPLETED,
                    'video_data': video_base64,
                    'completed_at': datetime.now(),
                    'updated_at': datetime.now(),
                    'message': 'Video processing completed successfully'
                })
                
        except Exception as e:
            logger.error(f"Error processing video task {task_id}: {e}", exc_info=True)
            self.tasks[task_id].update({
                'status': TaskStatus.FAILED,
                'error': str(e),
                'updated_at': datetime.now(),
                'message': f'Video processing failed: {str(e)}'
            })
    
    async def _download_videos(self, video_urls: list[str], temp_dir: str) -> list[str]:
        """Download videos from URLs"""
        import httpx
        
        video_files = []
        async with httpx.AsyncClient() as client:
            for i, url in enumerate(video_urls):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    
                    video_file = os.path.join(temp_dir, f"video_{i}.mp4")
                    with open(video_file, 'wb') as f:
                        f.write(response.content)
                    video_files.append(video_file)
                    
                except Exception as e:
                    raise Exception(f"Failed to download video {url}: {str(e)}")
        
        return video_files
    
    def _save_audio_data(self, audio_data: str, temp_dir: str) -> str:
        """Save base64 audio data to file"""
        try:
            audio_bytes = base64.b64decode(audio_data)
            audio_file = os.path.join(temp_dir, "audio.mp3")
            with open(audio_file, 'wb') as f:
                f.write(audio_bytes)
            return audio_file
        except Exception as e:
            raise Exception(f"Failed to save audio data: {str(e)}")
    
    def _create_subtitle_file(self, subtitle_srt: str, temp_dir: str) -> str:
        """Save SRT subtitle content to file and convert to ASS format for better compatibility"""
        subtitle_file = os.path.join(temp_dir, "subtitles.srt")
        ass_file = os.path.join(temp_dir, "subtitles.ass")
        
        # Write the SRT content directly to file
        with open(subtitle_file, 'w', encoding='utf-8') as f:
            f.write(subtitle_srt)
        
        # Convert SRT to ASS format using FFmpeg for better compatibility
        cmd = [
            'ffmpeg', '-y',
            '-i', subtitle_file,
            ass_file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
        
        if result.returncode != 0:
            logger.warning(f"Failed to convert SRT to ASS, using SRT directly: {result.stderr}")
            return subtitle_file
        
        return ass_file
    
    def _merge_videos(self, video_files: list[str], temp_dir: str, output_resolution: str) -> str:
        """Merge multiple videos using ffmpeg"""
        if len(video_files) == 1:
            return video_files[0]
        
        # Create file list for ffmpeg
        file_list = os.path.join(temp_dir, "file_list.txt")
        with open(file_list, 'w') as f:
            for video_file in video_files:
                f.write(f"file '{video_file}'\n")
        
        merged_video = os.path.join(temp_dir, "merged.mp4")
        
        # FFmpeg command to merge videos (all videos are already 1920x1080)
        cmd = [
            'ffmpeg', '-y',  # Overwrite output file
            '-f', 'concat',  # Use concat demuxer
            '-safe', '0',    # Allow unsafe file paths
            '-i', file_list, # Input file list
            '-c', 'copy',    # Copy streams without re-encoding
            merged_video
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg command failed: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            raise Exception(f"FFmpeg merge failed: {result.stderr}")
        
        return merged_video
    
    def _add_audio_and_subtitles(
        self,
        video_file: str,
        audio_file: str,
        subtitle_file: str,
        temp_dir: str,
        output_resolution: str
    ) -> str:
        """Add audio and embed subtitles in the video"""
        final_video = os.path.join(temp_dir, "final.mp4")
        
        # Use a more robust approach for Windows paths with FFmpeg
        # Create a relative path within the temp directory to avoid path issues
        subtitle_filename = os.path.basename(subtitle_file)
        
        # FFmpeg command to add audio and burn subtitles (video is already at correct resolution)
        # Use ASS filter for better compatibility with Windows paths
        if subtitle_filename.endswith('.ass'):
            subtitle_filter = f'ass={subtitle_filename}'
        else:
            subtitle_filter = f'subtitles={subtitle_filename}'
        
        cmd = [
            'ffmpeg', '-y',
            '-i', os.path.basename(video_file),    # Input video (relative path)
            '-i', os.path.basename(audio_file),    # Input audio (relative path)
            '-vf', subtitle_filter,                # Use ASS or subtitles filter
            '-c:v', 'libx264',          # Video codec (need to re-encode for subtitles)
            '-c:a', 'aac',              # Audio codec
            '-shortest',                # End when shortest input ends
            '-pix_fmt', 'yuv420p',      # Pixel format for compatibility
            os.path.basename(final_video)  # Output video (relative path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=temp_dir)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg command failed: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            raise Exception(f"FFmpeg audio/subtitle processing failed: {result.stderr}")
        
        return final_video
    
    def _add_audio_only(
        self,
        video_file: str,
        audio_file: str,
        temp_dir: str,
        output_resolution: str
    ) -> str:
        """Add audio to video without subtitles"""
        final_video = os.path.join(temp_dir, "final.mp4")
        
        # FFmpeg command to add audio only (video is already at correct resolution)
        cmd = [
            'ffmpeg', '-y',
            '-i', video_file,           # Input video
            '-i', audio_file,           # Input audio
            '-c:v', 'copy',             # Copy video stream (already at correct resolution)
            '-c:a', 'aac',              # Audio codec
            '-shortest',                # End when shortest input ends
            final_video
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            logger.error(f"FFmpeg command failed: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {result.stderr}")
            logger.error(f"FFmpeg stdout: {result.stdout}")
            raise Exception(f"FFmpeg audio processing failed: {result.stderr}")
        
        return final_video
    
    def _encode_video_to_base64(self, video_file: str) -> str:
        """Encode video file to base64"""
        try:
            with open(video_file, 'rb') as f:
                video_bytes = f.read()
            return base64.b64encode(video_bytes).decode('utf-8')
        except Exception as e:
            raise Exception(f"Failed to encode video to base64: {str(e)}")
    
    def _update_task_status(self, task_id: str, status: TaskStatus, message: str):
        """Update task status"""
        if task_id in self.tasks:
            self.tasks[task_id].update({
                'status': status,
                'message': message,
                'updated_at': datetime.now()
            })
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, Dict[str, Any]]:
        """Get all tasks"""
        return self.tasks.copy()


# Global instance
video_service = VideoProcessingService() 