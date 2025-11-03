<template>
  <div class="recording-control">
    <div class="container">
      <h1>회의 녹음 시스템</h1>

      <!-- 회의 정보 입력 폼 -->
      <div class="form-section" v-if="!isRecording">
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
          <label>참석자 (순서대로 Speaker 1, 2, 3...으로 매핑됩니다):</label>
          <div class="participants-container">
            <div
              v-for="(participant, index) in participants"
              :key="index"
              class="participant-row"
            >
              <div class="participant-number">{{ index + 1 }}</div>
              <input
                v-model="participants[index]"
                type="text"
                :placeholder="`참석자 ${index + 1} 이름`"
                class="input-field participant-input"
              />
              <button
                v-if="participants.length > 2"
                @click="removeParticipant(index)"
                class="btn-remove"
                type="button"
              >
                ✕
              </button>
            </div>
          </div>
          <button @click="addParticipant" class="btn-add" type="button">
            + 참석자 추가
          </button>
          <small class="help-text">순서대로 Speaker 1, Speaker 2... 로 자동 매핑됩니다</small>
        </div>

        <div class="form-group">
          <label for="language">언어:</label>
          <select id="language" v-model="formData.language" class="input-field">
            <option value="ko-KR">한국어</option>
            <option value="en-US">영어</option>
            <option value="ja-JP">일본어</option>
            <option value="zh-CN">중국어</option>
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
          <p v-if="formData.meeting_title">
            <strong>회의:</strong> {{ formData.meeting_title }}
          </p>
          <p><strong>시간:</strong> {{ formattedDuration }}</p>
        </div>

        <!-- 실시간 텍스트 표시 -->
        <div class="transcription-display" v-if="transcriptions.length > 0">
          <h3>인식된 텍스트:</h3>
          <div class="transcription-list">
            <div
              v-for="item in transcriptions"
              :key="item.id"
              class="transcription-item"
            >
              <strong v-if="item.speaker_changed" class="speaker-tag">
                [{{ item.speaker }}]
              </strong>
              <span>{{ item.text }}</span>
            </div>
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
      </div>

      <!-- 화자 매핑 모달 -->
      <div v-if="speakerMappingRequest" class="modal-overlay" @click.self="closeModal">
        <div class="modal">
          <h3>화자 확인</h3>

          <div class="speaker-text">
            "{{ speakerMappingRequest.text }}"
          </div>

          <p>이 발화는 누구의 발화인가요?</p>

          <select v-model="selectedSpeakerName" class="speaker-select">
            <option value="">선택하세요</option>
            <option
              v-for="name in speakerMappingRequest.available_names"
              :key="name"
              :value="name"
            >
              {{ name }}
            </option>
          </select>

          <div class="modal-buttons">
            <button
              @click="confirmSpeakerMapping"
              :disabled="!selectedSpeakerName"
              class="btn btn-primary"
            >
              확인
            </button>
          </div>
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
      meeting_title: '',
      language: 'ko-KR',
    });

    // 참석자 목록 (배열로 관리)
    const participants = ref(['', '']);

    const transcriptions = ref([]);
    const speakerMappingRequest = ref(null);
    const selectedSpeakerName = ref('');

    // 참석자 추가
    const addParticipant = () => {
      participants.value.push('');
    };

    // 참석자 제거
    const removeParticipant = (index) => {
      participants.value.splice(index, 1);
    };

    // MediaRecorder 관련
    let mediaRecorder = null;

    // 포맷된 녹음 시간
    const formattedDuration = computed(() => {
      const minutes = Math.floor(recordingDuration.value / 60);
      const seconds = recordingDuration.value % 60;
      return `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    });

    // 메시지 표시
    const showMessage = (message, type = 'info') => {
      statusMessage.value = message;
      messageType.value = type;
      setTimeout(() => {
        statusMessage.value = '';
      }, 5000);
    };

    // WebSocket 이벤트 핸들러 등록
    const setupWebSocketHandlers = () => {
      websocketService.on('status', (data) => {
        showMessage(data.message, 'success');
      });

      websocketService.on('transcription_recorded', (data) => {
        transcriptions.value.push({
          id: Date.now() + Math.random(),
          text: data.text,
          speaker: data.speaker,
          speaker_changed: data.speaker_changed
        });
        console.log('녹취 기록:', data.speaker, data.text);
      });

      websocketService.on('speaker_mapping_required', (data) => {
        speakerMappingRequest.value = {
          speaker_id: data.speaker_id,
          text: data.text,
          available_names: data.available_names
        };
        console.log('화자 매핑 필요:', data.speaker_id);
      });

      websocketService.on('speaker_mapped', (data) => {
        console.log('화자 매핑 완료:', data.speaker_id, '→', data.speaker_name);
        speakerMappingRequest.value = null;
        selectedSpeakerName.value = '';
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
      if (!formData.value.meeting_title.trim()) {
        showMessage('회의 제목을 입력해주세요', 'error');
        return;
      }

      // 참석자 검증 (최소 1명의 이름이 입력되어야 함)
      const validParticipants = participants.value.filter(p => p.trim() !== '');
      if (validParticipants.length === 0) {
        showMessage('최소 1명의 참석자를 입력해주세요', 'error');
        return;
      }

      try {
        isConnecting.value = true;
        completedData.value = null;
        transcriptions.value = [];

        // WebSocket 연결
        await websocketService.connect();
        setupWebSocketHandlers();

        // 회의 시작 요청 (참석자 배열을 쉼표로 구분된 문자열로 변환)
        const participantsStr = participants.value
          .filter(p => p.trim() !== '')
          .join(', ');

        websocketService.startRecording({
          meeting_title: formData.value.meeting_title,
          participants: participantsStr,
          language: formData.value.language
        });

        // 마이크 권한 요청
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            channelCount: 1,  // 모노
            sampleRate: 48000  // Google 권장
          }
        });

        // MediaRecorder 생성
        mediaRecorder = new MediaRecorder(stream, {
          mimeType: 'audio/webm;codecs=opus'
        });

        // 오디오 청크 수신 이벤트 (즉시 전송)
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            // Blob을 Base64로 변환하여 즉시 전송
            const reader = new FileReader();

            reader.onloadend = () => {
              // data:audio/webm;base64,ABC123... 형식
              // → ABC123... 부분만 추출
              const base64Data = reader.result.split(',')[1];

              // 서버로 즉시 전송 (Speech API 스트림에 직접 전달됨)
              websocketService.sendAudio(base64Data);

              console.log('오디오 청크 즉시 전송:', event.data.size, 'bytes');
            };

            reader.readAsDataURL(event.data);
          }
        };

        // 500ms마다 청크 생성 및 즉시 전송
        mediaRecorder.start(500);

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
      // MediaRecorder 정지
      if (mediaRecorder) {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
      }

      // 즉시 녹음 중 UI 종료
      isRecording.value = false;
      stopDurationTimer();

      // 서버에 종료 알림 (약간의 지연으로 마지막 청크 전송 보장)
      setTimeout(() => {
        websocketService.endRecording();
      }, 500);

      showMessage('회의를 종료하고 저장 중입니다...', 'info');
    };

    // 화자 매핑 확인
    const confirmSpeakerMapping = () => {
      if (!selectedSpeakerName.value) return;

      websocketService.sendSpeakerMapping(
        speakerMappingRequest.value.speaker_id,
        selectedSpeakerName.value
      );
    };

    // 모달 닫기
    const closeModal = () => {
      // 모달 배경 클릭 시에는 닫지 않음 (사용자가 명시적으로 선택해야 함)
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
      if (mediaRecorder) {
        mediaRecorder.stop();
        mediaRecorder.stream.getTracks().forEach(track => track.stop());
      }
      stopDurationTimer();
      if (processingInterval) {
        clearInterval(processingInterval);
      }
      websocketService.disconnect();
    });

    return {
      isRecording,
      isConnecting,
      formData,
      participants,
      addParticipant,
      removeParticipant,
      statusMessage,
      messageType,
      formattedDuration,
      transcriptions,
      completedData,
      speakerMappingRequest,
      selectedSpeakerName,
      startRecording,
      stopRecording,
      confirmSpeakerMapping,
      closeModal,
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

.help-text {
  display: block;
  margin-top: 0.25rem;
  font-size: 0.875rem;
  color: #888;
}

/* 참석자 입력 영역 */
.participants-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.participant-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.participant-number {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.9rem;
  flex-shrink: 0;
}

.participant-input {
  flex: 1;
  margin: 0;
}

.btn-add {
  width: 100%;
  padding: 0.75rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border: none;
  border-radius: 8px;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s;
  box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
  margin-bottom: 0.5rem;
}

.btn-add:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-remove {
  width: 32px;
  height: 32px;
  background: #ff4757;
  color: white;
  border: none;
  border-radius: 50%;
  font-size: 1.2rem;
  cursor: pointer;
  transition: all 0.3s;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.btn-remove:hover {
  background: #ff3838;
  transform: scale(1.1);
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
  padding: 0.5rem;
  background: #f0f0f0;
  border-radius: 6px;
  color: #333;
  line-height: 1.6;
}

.speaker-tag {
  color: #667eea;
  font-weight: 600;
  margin-right: 0.5rem;
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

/* 화자 매핑 모달 */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 2rem;
  border-radius: 12px;
  max-width: 500px;
  width: 90%;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
}

.modal h3 {
  margin-bottom: 1rem;
  color: #333;
}

.speaker-text {
  background: #f0f0f0;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-style: italic;
  color: #555;
  line-height: 1.6;
}

.speaker-select {
  width: 100%;
  padding: 0.75rem;
  border: 2px solid #e0e0e0;
  border-radius: 8px;
  font-size: 1rem;
  margin: 1rem 0;
}

.speaker-select:focus {
  outline: none;
  border-color: #667eea;
}

.modal-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 1rem;
  margin-top: 1rem;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  padding: 0.75rem 2rem;
  font-size: 1rem;
  font-weight: 600;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.3s;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
