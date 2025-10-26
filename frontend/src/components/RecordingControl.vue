<template>
  <div class="recording-control">
    <div class="container">
      <h1>회의 녹음 시스템</h1>

      <!-- 회의 정보 입력 폼 -->
      <div class="form-section" v-if="!isRecording">
        <div class="form-group">
          <label for="speaker">화자 이름:</label>
          <input
            id="speaker"
            v-model="formData.speaker"
            type="text"
            placeholder="이름을 입력하세요"
            class="input-field"
          />
        </div>

        <div class="form-group">
          <label for="meetingTitle">회의 제목:</label>
          <input
            id="meetingTitle"
            v-model="formData.meeting_title"
            type="text"
            placeholder="회의 제목을 입력하세요"
            class="input-field"
          />
        </div>

        <div class="form-group">
          <label for="language">언어:</label>
          <select id="language" v-model="formData.language" class="input-field">
            <option value="ko">한국어</option>
            <option value="en">영어</option>
            <option value="ja">일본어</option>
            <option value="zh">중국어</option>
          </select>
        </div>
      </div>

      <!-- 녹음 상태 표시 -->
      <div class="status-section" v-if="isRecording">
        <div class="recording-indicator">
          <span class="recording-dot"></span>
          <span class="recording-text">녹음 중...</span>
        </div>
        <div class="status-info">
          <p><strong>화자:</strong> {{ formData.speaker }}</p>
          <p v-if="formData.meeting_title">
            <strong>회의:</strong> {{ formData.meeting_title }}
          </p>
          <p><strong>시간:</strong> {{ formattedDuration }}</p>
        </div>

        <!-- 실시간 텍스트 표시 -->
        <div class="transcription-display" v-if="currentTranscription">
          <h3>인식된 텍스트:</h3>
          <div class="transcription-list">
            <p v-for="(text, index) in transcriptions" :key="index" class="transcription-item">
              {{ text }}
            </p>
          </div>
        </div>
      </div>

      <!-- 녹음 제어 버튼 -->
      <div class="button-section">
        <button
          v-if="!isRecording"
          @click="startRecording"
          :disabled="isConnecting"
          class="btn btn-start"
        >
          {{ isConnecting ? '연결 중...' : '회의 시작' }}
        </button>

        <button v-else @click="stopRecording" class="btn btn-stop">
          회의 종료
        </button>
      </div>

      <!-- 메시지 표시 -->
      <div v-if="statusMessage" class="message" :class="messageType">
        {{ statusMessage }}
      </div>

      <!-- 완료 결과 표시 -->
      <div v-if="completedData" class="result-section">
        <h3>✅ 회의 저장 완료!</h3>
        <div class="sheet-link-container">
          <p><strong>생성된 시트:</strong></p>
          <a :href="completedData.sheet_link" target="_blank" class="sheet-link">
            📄 Google Sheets에서 열기
          </a>
        </div>
        <p><strong>녹취 개수:</strong> {{ completedData.transcription_count }}개</p>
        <div class="transcription-result">
          <h4>전체 녹취록:</h4>
          <p>{{ completedData.transcription }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onUnmounted } from 'vue';
import websocketService from '../services/websocket.js';

export default {
  name: 'RecordingControl',
  setup() {
    const isRecording = ref(false);
    const isConnecting = ref(false);
    const statusMessage = ref('');
    const messageType = ref('info');
    const recordingDuration = ref(0);
    const durationInterval = ref(null);
    const completedData = ref(null);

    const formData = ref({
      speaker: '',
      meeting_title: '',
      language: 'ko',
    });

    const transcriptions = ref([]);
    const currentTranscription = ref('');

    // 브라우저 음성 인식 (Web Speech API)
    let recognition = null;

    // 포맷된 녹음 시간
    const formattedDuration = computed(() => {
      const minutes = Math.floor(recordingDuration.value / 60);
      const seconds = recordingDuration.value % 60;
      return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    });

    // 브라우저 음성 인식 초기화
    const initSpeechRecognition = () => {
      if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        showMessage('이 브라우저는 음성 인식을 지원하지 않습니다', 'error');
        return null;
      }

      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      const recognitionInstance = new SpeechRecognition();

      recognitionInstance.continuous = true;
      recognitionInstance.interimResults = false;
      recognitionInstance.lang = formData.value.language === 'ko' ? 'ko-KR' :
                                 formData.value.language === 'en' ? 'en-US' :
                                 formData.value.language === 'ja' ? 'ja-JP' : 'zh-CN';

      recognitionInstance.onresult = (event) => {
        const last = event.results.length - 1;
        const transcript = event.results[last][0].transcript;

        console.log('음성 인식 결과:', transcript);
        transcriptions.value.push(transcript);
        currentTranscription.value = transcript;

        // WebSocket으로 텍스트 전송
        websocketService.sendTranscription(transcript);
      };

      recognitionInstance.onerror = (event) => {
        console.error('음성 인식 에러:', event.error);
        if (event.error !== 'no-speech') {
          showMessage(`음성 인식 오류: ${event.error}`, 'error');
        }
      };

      recognitionInstance.onend = () => {
        console.log('음성 인식 종료');
        // 녹음 중이면 자동으로 재시작
        if (isRecording.value) {
          try {
            recognitionInstance.start();
          } catch (e) {
            console.log('음성 인식 재시작 실패:', e);
          }
        }
      };

      return recognitionInstance;
    };

    // 메시지 표시
    const showMessage = (message, type = 'info') => {
      statusMessage.value = message;
      messageType.value = type;
      setTimeout(() => {
        statusMessage.value = '';
      }, 5000);
    };

    // WebSocket 메시지 핸들러 등록
    const setupWebSocketHandlers = () => {
      websocketService.on('status', (data) => {
        showMessage(data.message, 'success');
      });

      websocketService.on('transcription_received', (data) => {
        console.log('텍스트 수신 확인:', data.text);
      });

      websocketService.on('completed', (data) => {
        completedData.value = data;
        showMessage(data.message, 'success');
        isRecording.value = false;
        stopDurationTimer();
      });

      websocketService.on('error', (data) => {
        showMessage(data.message, 'error');
      });
    };

    // 녹음 시작
    const startRecording = async () => {
      if (!formData.value.speaker.trim()) {
        showMessage('화자 이름을 입력해주세요', 'error');
        return;
      }

      try {
        isConnecting.value = true;
        completedData.value = null;
        transcriptions.value = [];

        // WebSocket 연결
        await websocketService.connect();
        setupWebSocketHandlers();

        // 녹음 시작 요청
        websocketService.startRecording(formData.value);

        // 음성 인식 시작
        recognition = initSpeechRecognition();
        if (recognition) {
          recognition.start();
        }

        isRecording.value = true;
        isConnecting.value = false;
        startDurationTimer();
        showMessage('회의가 시작되었습니다', 'success');
      } catch (error) {
        console.error('녹음 시작 실패:', error);
        showMessage('연결 실패: ' + error.message, 'error');
        isConnecting.value = false;
      }
    };

    // 녹음 종료
    const stopRecording = () => {
      if (recognition) {
        recognition.stop();
        recognition = null;
      }

      websocketService.endRecording();
      stopDurationTimer();
      showMessage('회의를 종료하고 저장 중입니다...', 'info');
    };

    // 녹음 시간 타이머 시작
    const startDurationTimer = () => {
      recordingDuration.value = 0;
      durationInterval.value = setInterval(() => {
        recordingDuration.value++;
      }, 1000);
    };

    // 녹음 시간 타이머 중지
    const stopDurationTimer = () => {
      if (durationInterval.value) {
        clearInterval(durationInterval.value);
        durationInterval.value = null;
      }
    };

    // 컴포넌트 언마운트 시 정리
    onUnmounted(() => {
      if (recognition) {
        recognition.stop();
      }
      stopDurationTimer();
      websocketService.disconnect();
    });

    return {
      isRecording,
      isConnecting,
      formData,
      statusMessage,
      messageType,
      formattedDuration,
      transcriptions,
      currentTranscription,
      completedData,
      startRecording,
      stopRecording,
    };
  },
};
</script>

<style scoped>
.recording-control {
  min-height: 100vh;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  padding: 2rem;
}

.container {
  max-width: 800px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  padding: 2rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 2rem;
  font-size: 2rem;
}

.form-section {
  margin-bottom: 2rem;
}

.form-group {
  margin-bottom: 1.5rem;
}

.form-group label {
  display: block;
  margin-bottom: 0.5rem;
  color: #555;
  font-weight: 500;
}

.input-field {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  transition: border-color 0.3s;
}

.input-field:focus {
  outline: none;
  border-color: #667eea;
}

.status-section {
  background: #f8f9fa;
  padding: 1.5rem;
  border-radius: 12px;
  margin-bottom: 2rem;
}

.recording-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 1rem;
}

.recording-dot {
  width: 12px;
  height: 12px;
  background: #ff4757;
  border-radius: 50%;
  margin-right: 0.5rem;
  animation: pulse 1.5s infinite;
}

@keyframes pulse {
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.5;
  }
}

.recording-text {
  font-size: 1.2rem;
  font-weight: 600;
  color: #ff4757;
}

.status-info {
  text-align: center;
  margin-bottom: 1rem;
}

.status-info p {
  margin: 0.5rem 0;
  color: #555;
}

.transcription-display {
  margin-top: 1.5rem;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  max-height: 300px;
  overflow-y: auto;
}

.transcription-display h3 {
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
}

.transcription-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.transcription-item {
  padding: 0.75rem;
  background: #f0f0f0;
  border-radius: 6px;
  margin: 0;
  color: #333;
  line-height: 1.5;
}

.button-section {
  text-align: center;
  margin: 2rem 0;
}

.btn {
  padding: 1rem 3rem;
  font-size: 1.2rem;
  font-weight: 600;
  border: none;
  border-radius: 50px;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
}

.btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
  transform: none;
}

.btn-start {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-stop {
  background: linear-gradient(135deg, #ff4757 0%, #ff6348 100%);
  color: white;
}

.message {
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  text-align: center;
  font-weight: 500;
}

.message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}

.message.info {
  background: #d1ecf1;
  color: #0c5460;
  border: 1px solid #bee5eb;
}

.result-section {
  background: #e8f5e9;
  padding: 1.5rem;
  border-radius: 12px;
  margin-top: 2rem;
}

.result-section h3 {
  color: #2e7d32;
  margin-bottom: 1rem;
  text-align: center;
}

.sheet-link-container {
  margin: 1rem 0;
  padding: 1rem;
  background: white;
  border-radius: 8px;
  text-align: center;
}

.sheet-link {
  display: inline-block;
  margin-top: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: linear-gradient(135deg, #4285f4 0%, #34a853 100%);
  color: white;
  text-decoration: none;
  border-radius: 8px;
  font-weight: 600;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(66, 133, 244, 0.3);
}

.sheet-link:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(66, 133, 244, 0.5);
}

.transcription-result {
  margin-top: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 8px;
}

.transcription-result h4 {
  color: #555;
  margin-bottom: 0.5rem;
}

.transcription-result p {
  color: #333;
  line-height: 1.6;
  white-space: pre-wrap;
}
</style>
