import { useEffect, useRef, useState } from "react";

import {
  type SpeechRecognitionConstructor,
  type SpeechRecognitionLike,
} from "@/lib/utils";

export function useDictation({
  input,
  setInput,
  setError,
}: {
  input: string;
  setInput: (value: string) => void;
  setError: (error: string | null) => void;
}) {
  const [listening, setListening] = useState(false);
  const [speechRiskAccepted, setSpeechRiskAccepted] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  function stopDictation() {
    recognitionRef.current?.stop();
  }

  function toggleDictation() {
    if (listening) {
      stopDictation();
      return;
    }
    if (
      !speechRiskAccepted &&
      !window.confirm(
        "浏览器语音转写可能调用浏览器或系统的在线语音服务。请勿口述密码、API Key 或其他敏感信息。是否继续？",
      )
    ) {
      return;
    }

    setSpeechRiskAccepted(true);
    const speechWindow = window as typeof window & {
      SpeechRecognition?: SpeechRecognitionConstructor;
      webkitSpeechRecognition?: SpeechRecognitionConstructor;
    };
    const Recognition =
      speechWindow.SpeechRecognition || speechWindow.webkitSpeechRecognition;
    if (!Recognition) {
      setError("当前浏览器不支持语音转写，请使用 Edge / Chrome 或继续键盘输入。");
      return;
    }

    const instance = new Recognition();
    const originalInput = input.trim();
    recognitionRef.current = instance;
    instance.lang = "zh-CN";
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (event) => {
      let transcript = "";
      for (let index = 0; index < event.results.length; index += 1) {
        transcript += event.results[index][0].transcript;
      }
      setInput(
        originalInput
          ? `${originalInput} ${transcript}`.trim()
          : transcript.trim(),
      );
    };
    instance.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "麦克风权限未开启，Jarvis 无法开始聆听。"
          : `语音转写中断：${event.error}`,
      );
    };
    instance.onend = () => {
      setListening(false);
      recognitionRef.current = null;
    };
    setError(null);
    setListening(true);
    instance.start();
  }

  useEffect(
    () => () => {
      recognitionRef.current?.stop();
    },
    [],
  );

  return {
    listening,
    speechRiskAccepted,
    toggleDictation,
    stopDictation,
  };
}
