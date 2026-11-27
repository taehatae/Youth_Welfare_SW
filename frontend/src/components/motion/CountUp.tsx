import { useCountUp } from "../../hooks/useCountUp"

// 숫자만 렌더한다. 첫 렌더는 최종값이라 서버 렌더·테스트에서도 실제 숫자가 보인다.
export default function CountUp({ value }: { value: number }) {
  return <>{useCountUp(value)}</>
}
