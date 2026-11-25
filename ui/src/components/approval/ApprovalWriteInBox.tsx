// ui/src/components/approval/ApprovalWriteInBox.tsx
// @ai-rules:
// 1. [Constraint]: Component must be <= 100 lines.
// 2. [Pattern]: Provide textarea + clipboard screenshot paste preview.

import { resizeImage } from '../../utils/imageResize';

interface Props {
  text: string;
  setText: (v: string) => void;
  image: string | null;
  setImage: (v: string | null) => void;
  disabled: boolean;
}

export function ApprovalWriteInBox({ text, setText, image, setImage, disabled }: Props) {
  const handlePaste = async (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData.items;
    for (let i = 0; i < items.length; i++) {
      if (items[i].type.indexOf('image') !== -1) {
        const file = items[i].getAsFile();
        if (file) {
          e.preventDefault();

          const resized = await resizeImage(file, 1024, 1_400_000);
          if (resized) {
            setImage(resized);
          } else {
            const reader = new FileReader();
            reader.onload = () => setImage(reader.result as string);
            reader.readAsDataURL(file);
          }
          return;
        }
      }
    }
  };

  return (
    <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onPaste={handlePaste}
        disabled={disabled}
        placeholder="Provide instructions..."
        style={{ width: '100%', height: 60, padding: 8, borderRadius: 4, border: '1px solid #475569', background: '#1e293b', color: '#f8fafc', fontSize: 13, resize: 'vertical' }}
      />
      {image && (
        <div style={{ position: 'relative', display: 'inline-block', width: 'fit-content' }}>
          <img src={image} alt="Pasted attachment" style={{ maxHeight: 150, borderRadius: 4, border: '1px solid #475569' }} />
          <button
            type="button"
            onClick={() => setImage(null)}
            style={{ position: 'absolute', top: 4, right: 4, background: '#ef4444', color: 'white', border: 'none', borderRadius: '50%', width: 20, height: 20, cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}
