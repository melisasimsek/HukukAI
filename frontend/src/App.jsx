import { useEffect, useRef, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000/sor";
const DILEKCE_API_URL =
  "http://127.0.0.1:8000/dilekce-olustur";

function App() {
  const [chats, setChats] = useState(() => {
    try {
      const saved = localStorage.getItem("hukukai_chats");

      if (saved) {
        const parsed = JSON.parse(saved);

        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch (error) {
      console.error("Sohbet geçmişi okunamadı:", error);
    }

    return [
      {
        id: Date.now(),
        title: "Yeni sohbet",
        messages: [],
      },
    ];
  });

  const [activeChatId, setActiveChatId] = useState(() => {
    const saved = localStorage.getItem("hukukai_active_chat");

    if (saved) {
      return Number(saved);
    }

    return null;
  });

  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [sayfa, setSayfa] = useState("sohbet");
const [mevzuatSorgu, setMevzuatSorgu] = useState("");
const [mevzuatSonuclari, setMevzuatSonuclari] = useState([]);
const [mevzuatLoading, setMevzuatLoading] = useState(false);
const [dilekceAdSoyad, setDilekceAdSoyad] = useState("");
const [dilekceIsveren, setDilekceIsveren] = useState("");
const [dilekceTarih, setDilekceTarih] = useState("");
const [dilekceMakam, setDilekceMakam] = useState("");


  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  const activeChat =
    chats.find((chat) => chat.id === activeChatId) || chats[0];

  useEffect(() => {
    localStorage.setItem("hukukai_chats", JSON.stringify(chats));
  }, [chats]);

  useEffect(() => {
    if (activeChat) {
      setActiveChatId((current) => {
        if (current === activeChat.id) {
          return current;
        }

        return activeChat.id;
      });

      localStorage.setItem(
        "hukukai_active_chat",
        String(activeChat.id)
      );
    }
  }, [activeChat]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [activeChat?.messages, loading]);

  // --------------------------------------------------
  // YENİ SOHBET
  // --------------------------------------------------

  const yeniSohbet = () => {
    const newChat = {
      id: Date.now(),
      title: "Yeni sohbet",
      messages: [],
    };

    setChats((prev) => [newChat, ...prev]);
    setActiveChatId(newChat.id);
    setQuestion("");

    setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
  };

  // --------------------------------------------------
  // SOHBET SEÇ
  // --------------------------------------------------

  const sohbetSec = (id) => {
    setActiveChatId(id);
    setQuestion("");
  };

  // --------------------------------------------------
  // SOHBET SİL
  // --------------------------------------------------

  const sohbetSil = (id, event) => {
    event.stopPropagation();

    const chat = chats.find((item) => item.id === id);

    if (!chat) {
      return;
    }

    const onay = window.confirm(
      `"${chat.title}" sohbetini silmek istediğinize emin misiniz?`
    );

    if (!onay) {
      return;
    }

    const kalanSohbetler = chats.filter(
      (item) => item.id !== id
    );

    if (activeChatId === id) {
      if (kalanSohbetler.length > 0) {
        setActiveChatId(kalanSohbetler[0].id);
      } else {
        const yeni = {
          id: Date.now(),
          title: "Yeni sohbet",
          messages: [],
        };

        setChats([yeni]);
        setActiveChatId(yeni.id);
        return;
      }
    }

    setChats(kalanSohbetler);
  };

  // --------------------------------------------------
  // SOHBET YENİDEN ADLANDIR
  // --------------------------------------------------

  const sohbetYenidenAdlandir = (id, event) => {
    event.stopPropagation();

    const chat = chats.find((item) => item.id === id);

    if (!chat) {
      return;
    }

    const yeniBaslik = window.prompt(
      "Yeni sohbet adı:",
      chat.title
    );

    if (yeniBaslik === null) {
      return;
    }

    const temizBaslik = yeniBaslik.trim();

    if (!temizBaslik) {
      return;
    }

    setChats((prev) =>
      prev.map((item) =>
        item.id === id
          ? {
              ...item,
              title: temizBaslik,
            }
          : item
      )
    );
  };

  // --------------------------------------------------
  // SORU GÖNDER
  // --------------------------------------------------

  const soruGonder = async () => {
    const temizSoru = question.trim();

    if (!temizSoru || loading) {
      return;
    }

    let chatId = activeChat?.id;

    if (!chatId) {
      const newChat = {
        id: Date.now(),
        title: temizSoru.slice(0, 35),
        messages: [],
      };

      setChats((prev) => [newChat, ...prev]);
      setActiveChatId(newChat.id);

      chatId = newChat.id;
    }

    const userMessage = {
      id: Date.now(),
      role: "user",
      content: temizSoru,
    };

    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id !== chatId) {
          return chat;
        }

        return {
          ...chat,
          title:
            chat.messages.length === 0
              ? temizSoru.slice(0, 35)
              : chat.title,
          messages: [
            ...chat.messages,
            userMessage,
          ],
        };
      })
    );

    setQuestion("");
    setLoading(true);

    try {
      const response = await fetch(API_URL, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          soru: temizSoru,
        }),
      });

      if (!response.ok) {
        throw new Error("Sunucu cevap vermedi.");
      }

      const data = await response.json();

      const assistantMessage = {
        id: Date.now() + 1,
        role: "assistant",
        content:
          data.cevap || "Cevap alınamadı.",
        sources: data.kaynaklar || [],
      };

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== chatId) {
            return chat;
          }

          return {
            ...chat,
            messages: [
              ...chat.messages,
              assistantMessage,
            ],
          };
        })
      );
    } catch (error) {
      console.error(error);

      const errorMessage = {
        id: Date.now() + 2,
        role: "assistant",
        content:
          "Backend'e bağlanırken bir hata oluştu. FastAPI sunucusunun çalıştığından emin olun.",
        sources: [],
        error: true,
      };

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== chatId) {
            return chat;
          }

          return {
            ...chat,
            messages: [
              ...chat.messages,
              errorMessage,
            ],
          };
        })
      );
    } finally {
      setLoading(false);
    }
  };
  // --------------------------------------------------
  // DİLEKÇE OLUŞTUR
  // --------------------------------------------------

  const dilekceOlustur = async (messageId) => {
    if (!activeChat) {
      return;
    }

    const messageIndex = activeChat.messages.findIndex(
      (message) => message.id === messageId
    );

    if (messageIndex === -1) {
      return;
    }

    const assistantMessage =
      activeChat.messages[messageIndex];

    let userQuestion = "";

    for (let i = messageIndex - 1; i >= 0; i--) {
      if (activeChat.messages[i].role === "user") {
        userQuestion =
          activeChat.messages[i].content;
        break;
      }
    }

    if (!userQuestion) {
      return;
    }

    setChats((prev) =>
      prev.map((chat) => {
        if (chat.id !== activeChat.id) {
          return chat;
        }

        return {
          ...chat,
          messages: chat.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  dilekceLoading: true,
                  dilekceError: false,
                }
              : message
          ),
        };
      })
    );

    try {
      const response = await fetch(
        DILEKCE_API_URL,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            soru: userQuestion,
            cevap: assistantMessage.content,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          "Dilekçe oluşturulamadı."
        );
      }

      const data = await response.json();

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== activeChat.id) {
            return chat;
          }

          return {
            ...chat,
            messages: chat.messages.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    dilekceLoading: false,
                    dilekceError: false,
                  dilekce: {
  baslik: data.baslik || "Başvuru Taslağı",
  metin: data.dilekce || "",
  kaynaklar: data.kaynaklar || [],
},
}
: message
            ),
          };
        })
      );
    } catch (error) {
      console.error(
        "Dilekçe oluşturma hatası:",
        error
      );

      setChats((prev) =>
        prev.map((chat) => {
          if (chat.id !== activeChat.id) {
            return chat;
          }

          return {
            ...chat,
            messages: chat.messages.map((message) =>
              message.id === messageId
                ? {
                    ...message,
                    dilekceLoading: false,
                    dilekceError: true,
                  }
                : message
            ),
          };
        })
      );
    }
  };


  const dilekceKopyala = async (metin) => {
    try {
      await navigator.clipboard.writeText(
        metin
      );

      window.alert(
        "Dilekçe taslağı panoya kopyalandı."
      );
    } catch (error) {
      console.error(
        "Kopyalama hatası:",
        error
      );

      window.alert(
        "Dilekçe kopyalanamadı."
      );
    }
  };


  const dilekceBilgileriUygula = (messageId) => {
  setChats((prevChats) =>
    prevChats.map((chat) => {
      if (chat.id !== activeChatId) {
        return chat;
      }

      return {
        ...chat,
        messages: chat.messages.map((message) => {
          if (message.id !== messageId || !message.dilekce) {
            return message;
          }

          let yeniMetin = message.dilekce.metin;

          const makam = dilekceMakam.trim();
          const adSoyad = dilekceAdSoyad.trim();
          const isveren = dilekceIsveren.trim();
          let tarih = dilekceTarih.trim();

          // Tarihi 01.02.2003 formatına çevir
          if (tarih) {
            const [yil, ay, gun] = tarih.split("-");
            tarih = `${gun}.${ay}.${yil}`;
          }

          // İlgili makam
          if (makam) {
            yeniMetin = yeniMetin.replaceAll(
              "[İLGİLİ MAKAMA]",
              makam
            );
          }

          // Ad Soyad
          if (adSoyad) {
            yeniMetin = yeniMetin.replaceAll(
              "[AD SOYAD]",
              adSoyad
            );
          }

          // İşveren / Şirket
          if (isveren) {
            yeniMetin = yeniMetin.replaceAll(
              "[İŞVEREN / ŞİRKET ADI]",
              isveren
            );
          }

          // Tarih
          if (tarih) {
            yeniMetin = yeniMetin.replaceAll(
              "[TARİH]",
              tarih
            );
          }

          return {
            ...message,
            dilekce: {
              ...message.dilekce,
              metin: yeniMetin,
            },
          };
        }),
      };
    })
  );
};
    const dilekceIndir = async (dilekce, format) => {
    try {
      const endpoint =
        format === "pdf"
          ? "http://127.0.0.1:8000/dilekce-pdf"
          : "http://127.0.0.1:8000/dilekce-word";

      const response = await fetch(endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          baslik: dilekce.baslik,
          dilekce: dilekce.metin,
        }),
      });

      if (!response.ok) {
        throw new Error(`Dosya oluşturulamadı: ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;

      link.download =
        format === "pdf"
          ? "dilekce_taslagi.pdf"
          : "dilekce_taslagi.docx";

      document.body.appendChild(link);
      link.click();
      link.remove();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Dilekçe indirme hatası:", error);
      window.alert(
        "Dilekçe dosyası indirilemedi. Lütfen tekrar deneyin."
      );
    }
  };
  // --------------------------------------------------
// MEVZUAT ARA
// --------------------------------------------------

const mevzuatAra = async () => {
  const sorgu = mevzuatSorgu.trim();

  if (!sorgu || mevzuatLoading) {
    return;
  }

  setMevzuatLoading(true);

  try {
    const response = await fetch(
      `http://127.0.0.1:8000/mevzuat-ara?q=${encodeURIComponent(sorgu)}`
    );

    if (!response.ok) {
      throw new Error("Mevzuat araması başarısız.");
    }

    const data = await response.json();

    setMevzuatSonuclari(
      data.sonuclar || []
    );
  } catch (error) {
    console.error(error);
    setMevzuatSonuclari([]);
  } finally {
    setMevzuatLoading(false);
  }
};
  // --------------------------------------------------
  // ENTER
  // --------------------------------------------------

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      soruGonder();
    }
  };

  // --------------------------------------------------
  // CEVAP FORMAT
  // --------------------------------------------------
  const temizMetin = (text) => {
  if (!text) return "";

  return text
    .replace(/ /gi, " ")
    .replace(/ /g, " ")
    .replace(/ /gi, " ")
    .replace(/\r?\n/g, " ")
    .replace(/\s+/g, " ")
    .trim();
};
  const formatCevap = (text) => {
    if (!text) {
      return null;
    }

    const lines = text.split("\n");

    return lines.map((line, index) => (
      <span key={index}>
        {line}
        {index !== lines.length - 1 && <br />}
      </span>
    ));
  };

  // --------------------------------------------------
  // ARAYÜZ
  // --------------------------------------------------

  return (
  <div className="app">

    <div className="page-switch">
      <button
        className={sayfa === "sohbet" ? "active" : ""}
        onClick={() => setSayfa("sohbet")}
      >
        💬 HukukAI
      </button>

      <button
        className={sayfa === "mevzuat" ? "active" : ""}
        onClick={() => setSayfa("mevzuat")}
      >
        📚 Mevzuat Ara
      </button>
    </div>
    {sayfa === "mevzuat" && (
  <div className="mevzuat-page">
    <div className="mevzuat-container">

      <h1>Mevzuat Ara</h1>
      <p className="mevzuat-description">
        Kanun numarası, kanun adı veya madde numarası ile mevzuatta arama yapın.
      </p>

      <div className="mevzuat-search">
        <input
          type="text"
          value={mevzuatSorgu}
          onChange={(e) => setMevzuatSorgu(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              mevzuatAra();
            }
          }}
          placeholder="Örn: 4857, İş Kanunu, Madde 46"
        />

        <button
          onClick={mevzuatAra}
          disabled={mevzuatLoading}
        >
          {mevzuatLoading ? "Aranıyor..." : "Ara"}
        </button>
      </div>

      <div className="mevzuat-results">
        {mevzuatSonuclari.map((sonuc, index) => (
          <details
            className="mevzuat-result-card"
            key={`${sonuc.kanun_no}-${sonuc.madde}-${index}`}
          >
            <summary>
              <div>
                <strong>{sonuc.kanun}</strong>
                <span>Madde {sonuc.madde}</span>
              </div>

              <span>Görüntüle</span>
            </summary>

            <div className="mevzuat-result-content">
              <p>{temizMetin(sonuc.icerik)}</p>
            </div>
          </details>
        ))}
      </div>

    </div>
  </div>
)}
      {/* SOL MENÜ */}

      <aside className="sidebar">

        <div className="sidebar-top">

          <div className="brand">

            <div className="brand-icon">
              ⚖️
            </div>

            <div>
              <div className="brand-name">
                HukukAI
              </div>

              <div className="brand-subtitle">
                Hukuk Asistanı
              </div>
            </div>

          </div>

          <button
            className="new-chat-button"
            onClick={yeniSohbet}
          >
            <span className="plus">
              +
            </span>

            <span>
              Yeni Sohbet
            </span>
          </button>

        </div>

        <div className="history-title">
          Sohbetler
        </div>

        <div className="chat-history">

          {chats.map((chat) => (

            <div
              key={chat.id}
              className={`chat-item-wrapper ${
                activeChat?.id === chat.id
                  ? "active"
                  : ""
              }`}
            >

              <button
                className="chat-item"
                onClick={() =>
                  sohbetSec(chat.id)
                }
              >

                <span className="chat-item-icon">
                  💬
                </span>

                <span className="chat-item-title">
                  {chat.title}
                </span>

              </button>

              <div className="chat-actions">

                <button
                  className="chat-action-button"
                  onClick={(e) =>
                    sohbetYenidenAdlandir(
                      chat.id,
                      e
                    )
                  }
                  title="Yeniden adlandır"
                >
                  ✏️
                </button>

                <button
                  className="chat-action-button delete"
                  onClick={(e) =>
                    sohbetSil(chat.id, e)
                  }
                  title="Sohbeti sil"
                >
                  🗑️
                </button>

              </div>

            </div>

          ))}

        </div>

        <div className="sidebar-bottom">

          <div className="sidebar-info">

            <span>
              ⚖️
            </span>

            <div>

              <strong>
                HukukAI
              </strong>

              <small>
                Yapay zekâ destekli hukuk asistanı
              </small>

            </div>

          </div>

        </div>

      </aside>

      {/* ANA ALAN */}

      <main className="main">

        <header className="topbar">

          <div>

            <h1>
              HukukAI
            </h1>

            <p>
              Yapay zekâ destekli hukuk asistanı
            </p>

          </div>

          <div className="status">

            <span className="status-dot"></span>

            Sistem aktif

          </div>

        </header>

        <section className="conversation">

          {activeChat?.messages?.length === 0 ? (

            <div className="welcome">

              <div className="welcome-icon">
                ⚖️
              </div>

              <h2>
                Hukuki sorunuz nedir?
              </h2>

              <p>
                Sorunuzu yazın, HukukAI ilgili
                kanun maddesini bulsun.
              </p>

              <div className="example-grid">

                <button
                  onClick={() =>
                    setQuestion(
                      "Deneme süresi en fazla ne kadar olabilir?"
                    )
                  }
                >
                  <span>
                    ⏱
                  </span>

                  <div>
                    <strong>
                      Deneme süresi
                    </strong>

                    <small>
                      Deneme süresi ne kadar olabilir?
                    </small>
                  </div>

                </button>

                <button
                  onClick={() =>
                    setQuestion(
                      "Yıllık ücretli izin hakkı ne zaman doğar?"
                    )
                  }
                >
                  <span>
                    📅
                  </span>

                  <div>
                    <strong>
                      Yıllık izin
                    </strong>

                    <small>
                      Yıllık izin hakkı ne zaman doğar?
                    </small>
                  </div>
                </button>

                <button
                  onClick={() =>
                    setQuestion(
                      "Yasal mirasçılar kimlerdir?"
                    )
                  }
                >
                  <span>
                    👨‍👩‍👧
                  </span>

                  <div>
                    <strong>
                      Yasal mirasçılar
                    </strong>

                    <small>
                      Kimler yasal mirasçıdır?
                    </small>
                  </div>
                </button>

                <button
                  onClick={() =>
                    setQuestion(
                      "İşçinin ücreti ne zaman ödenmelidir?"
                    )
                  }
                >
                  <span>
                    💰
                  </span>

                  <div>
                    <strong>
                      Ücret
                    </strong>

                    <small>
                      Ücret hangi sürede ödenmelidir?
                    </small>
                  </div>
                </button>

              </div>

            </div>

          ) : (

            <div className="messages">

              {activeChat.messages.map(
                (message) => (

                  <div
                    key={message.id}
                    className={`message-row ${
                      message.role === "user"
                        ? "user-row"
                        : "assistant-row"
                    }`}
                  >

                    <div
                      className={`avatar ${
                        message.role === "user"
                          ? "user-avatar"
                          : "ai-avatar"
                      }`}
                    >
                      {message.role === "user"
                        ? "S"
                        : "⚖️"}
                    </div>

                    <div className="message-content">

                      <div className="message-name">
                        {message.role === "user"
                          ? "Sen"
                          : "HukukAI"}
                      </div>

                      <div
                        className={`message-bubble ${
                          message.error
                            ? "error-message"
                            : ""
                        }`}
                      >
                        {formatCevap(
                          message.content
                        )}
                      </div>

                      {message.role ===
                        "assistant" &&
                        message.sources &&
                        message.sources.length > 0 && (

                          <div className="sources">

                            <div className="sources-title">
                              📚 Kaynak
                            </div>

                            {message.sources.map(
                              (
                                source,
                                index
                              ) => (

 <details
  className="source-card"
  key={index}
>
  <summary>
    <div className="source-info">
      <strong>{source.kanun}</strong>
      <span className="source-article">
        Madde {source.madde}
      </span>
    </div>

    <span className="source-open">
      Görüntüle
    </span>
  </summary>

  <div className="source-detail">
    <strong>Madde Metni</strong>
    <p>{source.icerik}</p>
  </div>
</details>

                              )
                            )}

                          </div>

                        )}

                        {message.role === "assistant" &&
                          !message.error &&
                          message.sources &&
                          message.sources.length > 0 && (
                            <div className="dilekce-area">
                              {!message.dilekce && (
                                <button
                                  className="dilekce-button"
                                  onClick={() => dilekceOlustur(message.id)}
                                  disabled={message.dilekceLoading}
                                >
                                  {message.dilekceLoading
                                    ? "⏳ Taslak hazırlanıyor..."
                                    : "📄 Dilekçe Taslağı Oluştur"}
                                </button>
                              )}

                              {message.dilekceError && (
                                <div className="dilekce-error">
                                  Dilekçe taslağı oluşturulamadı. Lütfen tekrar deneyin.
                                </div>
                              )}

                              {message.dilekce && (
                                <div className="dilekce-card">
                                  <div className="dilekce-header">
                                    <div>
                                      <span className="dilekce-label">📄 Dilekçe Taslağı</span>
                                      <h3>{message.dilekce.baslik}</h3>
                                    </div>
                                    <div className="dilekce-download-actions"
                                    
                                    
                                    
                                    
                                    >
  <button
    className="dilekce-copy-button"
    onClick={() => dilekceKopyala(message.dilekce.metin)}
  >
    📋 Kopyala
  </button>

  <button
    className="dilekce-copy-button"
    onClick={() => dilekceIndir(message.dilekce, "word")}
  >
    📝 Word İndir
  </button>

  <button
    className="dilekce-copy-button"
    onClick={() => dilekceIndir(message.dilekce, "pdf")}
  >
    📄 PDF İndir
  </button>
</div>
                                  </div>
<div className="dilekce-form">
  <div className="dilekce-form-title">
    ✍️ Dilekçe Bilgilerini Doldur
  </div>

  <div className="dilekce-form-grid">
    <div className="dilekce-form-field">
  <label>İlgili Makam</label>
  <input
    type="text"
    placeholder="Örn. Çalışma ve İş Kurumu İl Müdürlüğüne"
    value={dilekceMakam}
    onChange={(e) => setDilekceMakam(e.target.value)}
  />
</div>
    <div className="dilekce-form-field">
      <label>Ad Soyad</label>
      <input
  type="text"
  placeholder="Ad Soyad"
  value={dilekceAdSoyad}
  onChange={(e) => setDilekceAdSoyad(e.target.value)}
/>
    </div>

    <div className="dilekce-form-field">
      <label>İşveren / Şirket</label>
      <input
        type="text"
        placeholder="İşveren veya şirket adı"
        value={dilekceIsveren}
        onChange={(e) => setDilekceIsveren(e.target.value)}
      />
    </div>

    <div className="dilekce-form-field">
      <label>Tarih</label>
      <input
        type="date"
        value={dilekceTarih}
        onChange={(e) => setDilekceTarih(e.target.value)}
      />
    </div>
  </div>

  <button
    type="button"
    className="dilekce-update-button"
    onClick={() => dilekceBilgileriUygula(message.id)}
  >
    ✓ Dilekçeyi Güncelle
  </button>
</div>
                                  <div className="dilekce-edit-area">
  <div className="dilekce-edit-title">
  Dilekçe Metni
  <span>İsterseniz metni düzenleyebilirsiniz.</span>
</div>

  <textarea
    className="dilekce-edit-textarea"
    value={message.dilekce.metin}
    onChange={(e) => {
      const yeniMetin = e.target.value;

      setChats((prevChats) =>
        prevChats.map((chat) => {
          if (chat.id !== activeChatId) {
            return chat;
          }

          return {
            ...chat,
            messages: chat.messages.map((msg) =>
              msg.id === message.id
                ? {
                    ...msg,
                    dilekce: {
                      ...msg.dilekce,
                      metin: yeniMetin,
                    },
                  }
                : msg
            ),
          };
        })
      );
    }}
  />
</div>

                                  {message.dilekce.kaynaklar &&
                                    message.dilekce.kaynaklar.length > 0 && (
                                      <div className="dilekce-sources">
                                        <strong>📚 Kullanılan Kaynaklar</strong>
                                        {message.dilekce.kaynaklar.map((source, index) => (
                                          <div key={index} className="dilekce-source">
                                            {source.kanun} — Madde {source.madde}
                                          </div>
                                        ))}
                                      </div>
                                    )}
                                </div>
                              )}
                            </div>
                          )}

                    </div>

                  </div>

                )
              )}

              {loading && (

                <div className="message-row assistant-row">

                  <div className="avatar ai-avatar">
                    ⚖️
                  </div>

                  <div className="message-content">

                    <div className="message-name">
                      HukukAI
                    </div>

                    <div className="typing">

                      <span></span>
                      <span></span>
                      <span></span>

                    </div>

                  </div>

                </div>

              )}

              <div
                ref={messagesEndRef}
              ></div>

            </div>

          )}

        </section>

        {/* SORU ALANI */}

        <div className="input-area">

          <div className="input-wrapper">

            <textarea
              ref={textareaRef}
              value={question}
              onChange={(e) =>
                setQuestion(e.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder="Hukuki sorunuzu yazın..."
              rows="1"
            />

            <button
              className="send-button"
              onClick={soruGonder}
              disabled={
                !question.trim() ||
                loading
              }
            >
              ↑
            </button>

          </div>

          <div className="input-hint">
            Enter ile gönder • Shift + Enter ile yeni satır
          </div>

          <div className="disclaimer">
            HukukAI tarafından verilen bilgiler
            bilgilendirme amaçlıdır ve hukuki danışmanlık
            yerine geçmez.
          </div>

        </div>

      </main>

    </div>
  );


}

export default App;


