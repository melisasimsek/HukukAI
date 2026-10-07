import { useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  SafeAreaView,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import * as FileSystem from 'expo-file-system/legacy';
import * as Sharing from 'expo-sharing';

const API_URL = 'http://192.168.1.103:8000';

export default function HomeScreen() {
  const [activeTab, setActiveTab] =
    useState<'hukukai' | 'mevzuat'>('hukukai');

  const [question, setQuestion] = useState('');
  const [answer, setAnswer] = useState('');
  const [sources, setSources] = useState<any[]>([]);

  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);

  const [petitionTitle, setPetitionTitle] = useState('');
  const [petition, setPetition] = useState('');
  const [petitionSources, setPetitionSources] = useState<any[]>([]);

  const [petitionLoading, setPetitionLoading] = useState(false);
  const [isEditingPetition, setIsEditingPetition] = useState(false);
  const [fileLoading, setFileLoading] =
    useState<'word' | 'pdf' | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const askQuestion = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setAnswer('');
    setSources([]);

    setPetitionTitle('');
    setPetition('');
    setPetitionSources([]);
    setIsEditingPetition(false);

    setError('');

    try {
      const response = await fetch(`${API_URL}/sor`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          soru: question.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error('Sunucudan cevap alınamadı.');
      }

      const data = await response.json();

      setAnswer(data.cevap || '');
      setSources(data.kaynaklar || []);
    } catch (err) {
      console.error(err);

      setError(
        'HukukAI sunucusuna bağlanılamadı. Backend’in çalıştığından emin olun.'
      );
    } finally {
      setLoading(false);
    }
  };

  const createPetition = async () => {
    if (!question.trim() || !answer.trim()) return;

    setPetitionLoading(true);
    setPetitionTitle('');
    setPetition('');
    setPetitionSources([]);
    setIsEditingPetition(false);
    setError('');

    try {
      const response = await fetch(`${API_URL}/dilekce-olustur`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          soru: question.trim(),
          cevap: answer.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error('Dilekçe oluşturulamadı.');
      }

      const data = await response.json();

      setPetitionTitle(data.baslik || 'Dilekçe Taslağı');
      setPetition(data.dilekce || '');
      setPetitionSources(data.kaynaklar || []);
    } catch (err) {
      console.error(err);

      setError(
        'Dilekçe oluşturulurken bir hata oluştu. Backend’in çalıştığından emin olun.'
      );
    } finally {
      setPetitionLoading(false);
    }
  };

  const searchLegislation = async () => {
    if (!searchQuery.trim()) return;

    setLoading(true);
    setSearchResults([]);
    setError('');

    try {
      const response = await fetch(
        `${API_URL}/mevzuat-ara?q=${encodeURIComponent(
          searchQuery.trim()
        )}`
      );

      if (!response.ok) {
        throw new Error('Mevzuat araması yapılamadı.');
      }

      const data = await response.json();

      setSearchResults(data.sonuclar || []);
    } catch (err) {
      console.error(err);

      setError(
        'Mevzuat araması sırasında sunucuya bağlanılamadı.'
      );
    } finally {
      setLoading(false);
    }
  };

  const downloadPetition = async (type: 'word' | 'pdf') => {
    if (!petition.trim()) return;

    setFileLoading(type);
    setError('');

    try {
      const endpoint =
        type === 'word' ? '/dilekce-word' : '/dilekce-pdf';

      const extension = type === 'word' ? 'docx' : 'pdf';

      const response = await fetch(`${API_URL}${endpoint}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          baslik: petitionTitle.trim(),
          dilekce: petition.trim(),
        }),
      });

      if (!response.ok) {
        throw new Error(
          type === 'word'
            ? 'Word dosyası oluşturulamadı.'
            : 'PDF dosyası oluşturulamadı.'
        );
      }

      const blob = await response.blob();

      const reader = new FileReader();

      reader.onloadend = async () => {
        try {
          const result = reader.result;

          if (typeof result !== 'string') {
            throw new Error('Dosya okunamadı.');
          }

          const base64 = result.split(',')[1];

          if (!base64) {
            throw new Error('Dosya verisi alınamadı.');
          }

          const safeTitle =
            petitionTitle
              .replace(/[\\/:*?"<>|]/g, '')
              .replace(/\s+/g, '_')
              .slice(0, 40) || 'HukukAI_Dilekce';

          const fileUri =
            FileSystem.cacheDirectory +
            `${safeTitle}.${extension}`;

          await FileSystem.writeAsStringAsync(
            fileUri,
            base64,
            {
              encoding: FileSystem.EncodingType.Base64,
            }
          );

          const sharingAvailable =
            await Sharing.isAvailableAsync();

          if (!sharingAvailable) {
            Alert.alert(
              'Dosya oluşturuldu',
              'Dosya oluşturuldu ancak bu cihazda paylaşım özelliği kullanılamıyor.'
            );
            return;
          }

          await Sharing.shareAsync(fileUri, {
            mimeType:
              type === 'word'
                ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                : 'application/pdf',
            dialogTitle:
              type === 'word'
                ? 'Word dilekçesini paylaş'
                : 'PDF dilekçesini paylaş',
            UTI:
              type === 'word'
                ? 'org.openxmlformats.wordprocessingml.document'
                : 'com.adobe.pdf',
          });
        } catch (fileError) {
          console.error(fileError);

          setError(
            'Dosya telefonda hazırlanırken bir hata oluştu.'
          );
        } finally {
          setFileLoading(null);
        }
      };

      reader.onerror = () => {
        setFileLoading(null);
        setError('Dosya okunurken bir hata oluştu.');
      };

      reader.readAsDataURL(blob);
    } catch (err) {
      console.error(err);

      setFileLoading(null);

      setError(
        type === 'word'
          ? 'Word dosyası oluşturulurken bir hata oluştu.'
          : 'PDF dosyası oluşturulurken bir hata oluştu.'
      );
    }
  };

  const changeTab = (tab: 'hukukai' | 'mevzuat') => {
    setActiveTab(tab);
    setError('');
    setLoading(false);
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <View style={styles.logo}>
          <Text style={styles.logoIcon}>⚖️</Text>
        </View>

        <Text style={styles.title}>HukukAI</Text>

        <Text style={styles.subtitle}>
          Yapay zekâ destekli hukuk asistanı
        </Text>

        <View style={styles.tabs}>
          <TouchableOpacity
            style={[
              styles.tabButton,
              activeTab === 'hukukai' &&
                styles.activeTabButton,
            ]}
            onPress={() => changeTab('hukukai')}
          >
            <Text
              style={[
                styles.tabText,
                activeTab === 'hukukai' &&
                  styles.activeTabText,
              ]}
            >
              ⚖️ HukukAI
            </Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={[
              styles.tabButton,
              activeTab === 'mevzuat' &&
                styles.activeTabButton,
            ]}
            onPress={() => changeTab('mevzuat')}
          >
            <Text
              style={[
                styles.tabText,
                activeTab === 'mevzuat' &&
                  styles.activeTabText,
              ]}
            >
              📚 Mevzuat Ara
            </Text>
          </TouchableOpacity>
        </View>

        {activeTab === 'hukukai' && (
          <>
            <Text style={styles.sectionTitle}>
              Hukuki sorunuz nedir?
            </Text>

            <Text style={styles.description}>
              Sorunuzu yazın, HukukAI ilgili kanun maddelerini
              bulsun.
            </Text>

            <View style={styles.inputContainer}>
              <TextInput
                style={styles.largeInput}
                placeholder="Hukuki sorunuzu yazın..."
                placeholderTextColor="#9CA3AF"
                value={question}
                onChangeText={setQuestion}
                multiline
                editable={!loading}
              />

              <TouchableOpacity
                style={[
                  styles.sendButton,
                  (!question.trim() || loading) &&
                    styles.sendButtonDisabled,
                ]}
                disabled={!question.trim() || loading}
                onPress={askQuestion}
              >
                {loading ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.sendButtonText}>
                    Gönder
                  </Text>
                )}
              </TouchableOpacity>
            </View>

            {loading && (
              <Text style={styles.loadingText}>
                HukukAI ilgili kanun maddelerini araştırıyor...
              </Text>
            )}

            {answer !== '' && (
              <>
                <View style={styles.answerCard}>
                  <Text style={styles.answerTitle}>
                    ⚖️ HukukAI
                  </Text>

                  <Text style={styles.answerText}>
                    {answer}
                  </Text>
                </View>

                <TouchableOpacity
                  style={[
                    styles.petitionButton,
                    petitionLoading &&
                      styles.sendButtonDisabled,
                  ]}
                  disabled={petitionLoading}
                  onPress={createPetition}
                >
                  {petitionLoading ? (
                    <ActivityIndicator color="#FFFFFF" />
                  ) : (
                    <Text style={styles.petitionButtonText}>
                      📝 Dilekçe Oluştur
                    </Text>
                  )}
                </TouchableOpacity>
              </>
            )}

            {sources.length > 0 && (
              <View style={styles.sourcesCard}>
                <Text style={styles.sourcesTitle}>
                  📚 Kaynaklar
                </Text>

                {sources.map((source, index) => (
                  <View
                    key={`${source.kanun}-${source.madde}-${index}`}
                    style={styles.sourceItem}
                  >
                    <Text style={styles.sourceName}>
                      {source.kanun} — Madde {source.madde}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {petitionLoading && (
              <Text style={styles.loadingText}>
                Dilekçe taslağı hazırlanıyor...
              </Text>
            )}

            {petition !== '' && (
              <View style={styles.petitionCard}>
                <Text style={styles.petitionLabel}>
                  📝 Dilekçe Taslağı
                </Text>

                {isEditingPetition ? (
                  <>
                    <Text style={styles.editLabel}>
                      Dilekçe Başlığı
                    </Text>

                    <TextInput
                      style={styles.titleEditInput}
                      value={petitionTitle}
                      onChangeText={setPetitionTitle}
                      multiline
                    />

                    <Text style={styles.editLabel}>
                      Dilekçe Metni
                    </Text>

                    <TextInput
                      style={styles.petitionEditInput}
                      value={petition}
                      onChangeText={setPetition}
                      multiline
                      textAlignVertical="top"
                    />

                    <TouchableOpacity
                      style={styles.saveButton}
                      onPress={() =>
                        setIsEditingPetition(false)
                      }
                    >
                      <Text style={styles.saveButtonText}>
                        ✓ Düzenlemeyi Bitir
                      </Text>
                    </TouchableOpacity>
                  </>
                ) : (
                  <>
                    <Text style={styles.petitionTitle}>
                      {petitionTitle}
                    </Text>

                    <Text style={styles.petitionText}>
                      {petition}
                    </Text>

                    <TouchableOpacity
                      style={styles.editButton}
                      onPress={() =>
                        setIsEditingPetition(true)
                      }
                    >
                      <Text style={styles.editButtonText}>
                        ✏️ Düzenle
                      </Text>
                    </TouchableOpacity>
                  </>
                )}

                <View style={styles.downloadButtons}>
                  <TouchableOpacity
                    style={[
                      styles.fileButton,
                      fileLoading !== null &&
                        styles.sendButtonDisabled,
                    ]}
                    disabled={fileLoading !== null}
                    onPress={() =>
                      downloadPetition('word')
                    }
                  >
                    {fileLoading === 'word' ? (
                      <ActivityIndicator color="#172238" />
                    ) : (
                      <Text style={styles.fileButtonText}>
                        📄 Word
                      </Text>
                    )}
                  </TouchableOpacity>

                  <TouchableOpacity
                    style={[
                      styles.fileButton,
                      fileLoading !== null &&
                        styles.sendButtonDisabled,
                    ]}
                    disabled={fileLoading !== null}
                    onPress={() =>
                      downloadPetition('pdf')
                    }
                  >
                    {fileLoading === 'pdf' ? (
                      <ActivityIndicator color="#172238" />
                    ) : (
                      <Text style={styles.fileButtonText}>
                        📕 PDF
                      </Text>
                    )}
                  </TouchableOpacity>
                </View>

                {petitionSources.length > 0 && (
                  <View style={styles.petitionSources}>
                    <Text style={styles.sourcesTitle}>
                      📚 Dilekçe Kaynakları
                    </Text>

                    {petitionSources.map(
                      (source, index) => (
                        <View
                          key={`petition-${source.kanun}-${source.madde}-${index}`}
                          style={styles.sourceItem}
                        >
                          <Text style={styles.sourceName}>
                            {source.kanun} — Madde{' '}
                            {source.madde}
                          </Text>
                        </View>
                      )
                    )}
                  </View>
                )}
              </View>
            )}
          </>
        )}

        {activeTab === 'mevzuat' && (
          <>
            <Text style={styles.sectionTitle}>
              Mevzuatta Ara
            </Text>

            <Text style={styles.description}>
              Kanunlarda aramak istediğiniz kelime veya konuyu
              yazın.
            </Text>

            <View style={styles.searchContainer}>
              <TextInput
                style={styles.searchInput}
                placeholder="Örn: işçi ücret"
                placeholderTextColor="#9CA3AF"
                value={searchQuery}
                onChangeText={setSearchQuery}
                editable={!loading}
                onSubmitEditing={searchLegislation}
              />

              <TouchableOpacity
                style={[
                  styles.searchButton,
                  (!searchQuery.trim() || loading) &&
                    styles.sendButtonDisabled,
                ]}
                disabled={!searchQuery.trim() || loading}
                onPress={searchLegislation}
              >
                {loading ? (
                  <ActivityIndicator color="#FFFFFF" />
                ) : (
                  <Text style={styles.sendButtonText}>
                    Ara
                  </Text>
                )}
              </TouchableOpacity>
            </View>

            {loading && (
              <Text style={styles.loadingText}>
                Mevzuatta aranıyor...
              </Text>
            )}

            {searchResults.length > 0 && (
              <View style={styles.resultsContainer}>
                <Text style={styles.resultCount}>
                  {searchResults.length} sonuç bulundu
                </Text>

                {searchResults.map((result, index) => (
                  <View
                    key={`${result.kanun_no}-${result.madde}-${index}`}
                    style={styles.lawCard}
                  >
                    <Text style={styles.lawTitle}>
                      {result.kanun}
                    </Text>

                    <View style={styles.articleBadge}>
                      <Text style={styles.articleBadgeText}>
                        Madde {result.madde}
                      </Text>
                    </View>

                    <Text style={styles.lawContent}>
                      {result.icerik}
                    </Text>
                  </View>
                ))}
              </View>
            )}

            {!loading &&
              searchQuery.trim() !== '' &&
              searchResults.length === 0 &&
              error === '' && (
                <Text style={styles.emptyText}>
                  Arama yapmak için Ara butonuna basın.
                </Text>
              )}
          </>
        )}

        {error !== '' && (
          <View style={styles.errorCard}>
            <Text style={styles.errorText}>
              {error}
            </Text>
          </View>
        )}

        <Text style={styles.warning}>
          HukukAI tarafından verilen bilgiler genel
          bilgilendirme amaçlıdır.
        </Text>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F7F8FA',
  },

  content: {
    flexGrow: 1,
    alignItems: 'center',
    paddingHorizontal: 20,
    paddingTop: 45,
    paddingBottom: 50,
  },

  logo: {
    width: 68,
    height: 68,
    borderRadius: 19,
    backgroundColor: '#172238',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },

  logoIcon: {
    fontSize: 32,
  },

  title: {
    fontSize: 31,
    fontWeight: '700',
    color: '#111827',
  },

  subtitle: {
    fontSize: 15,
    color: '#7B8496',
    marginTop: 5,
  },

  tabs: {
    width: '100%',
    maxWidth: 650,
    flexDirection: 'row',
    backgroundColor: '#E9ECF1',
    borderRadius: 14,
    padding: 4,
    marginTop: 30,
    marginBottom: 35,
  },

  tabButton: {
    flex: 1,
    paddingVertical: 12,
    alignItems: 'center',
    borderRadius: 11,
  },

  activeTabButton: {
    backgroundColor: '#172238',
  },

  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: '#667085',
  },

  activeTabText: {
    color: '#FFFFFF',
  },

  sectionTitle: {
    fontSize: 25,
    fontWeight: '700',
    color: '#111827',
    textAlign: 'center',
  },

  description: {
    fontSize: 15,
    color: '#7B8496',
    textAlign: 'center',
    marginTop: 10,
    lineHeight: 22,
  },

  inputContainer: {
    width: '100%',
    maxWidth: 650,
    marginTop: 30,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 18,
    padding: 14,
  },

  largeInput: {
    minHeight: 90,
    fontSize: 16,
    color: '#111827',
    textAlignVertical: 'top',
    outlineWidth: 0,
  } as any,

  sendButton: {
    alignSelf: 'flex-end',
    backgroundColor: '#172238',
    paddingHorizontal: 22,
    paddingVertical: 12,
    borderRadius: 12,
    marginTop: 10,
    minWidth: 90,
    alignItems: 'center',
  },

  sendButtonDisabled: {
    opacity: 0.35,
  },

  sendButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 15,
  },

  loadingText: {
    marginTop: 20,
    fontSize: 14,
    color: '#7B8496',
    textAlign: 'center',
  },

  answerCard: {
    width: '100%',
    maxWidth: 650,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 18,
    padding: 20,
    marginTop: 25,
  },

  answerTitle: {
    fontSize: 17,
    fontWeight: '700',
    color: '#172238',
    marginBottom: 12,
  },

  answerText: {
    fontSize: 15,
    color: '#374151',
    lineHeight: 24,
  },

  petitionButton: {
    width: '100%',
    maxWidth: 650,
    backgroundColor: '#172238',
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 13,
    alignItems: 'center',
    marginTop: 14,
  },

  petitionButtonText: {
    color: '#FFFFFF',
    fontSize: 15,
    fontWeight: '700',
  },

  petitionCard: {
    width: '100%',
    maxWidth: 650,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 18,
    padding: 20,
    marginTop: 20,
  },

  petitionLabel: {
    fontSize: 14,
    fontWeight: '700',
    color: '#7B8496',
    marginBottom: 8,
  },

  petitionTitle: {
    fontSize: 19,
    fontWeight: '700',
    color: '#172238',
    lineHeight: 26,
    marginBottom: 18,
  },

  petitionText: {
    fontSize: 14,
    color: '#374151',
    lineHeight: 23,
  },

  editButton: {
    marginTop: 20,
    borderWidth: 1,
    borderColor: '#D5DAE1',
    borderRadius: 11,
    paddingVertical: 11,
    alignItems: 'center',
  },

  editButtonText: {
    color: '#172238',
    fontSize: 14,
    fontWeight: '700',
  },

  editLabel: {
    fontSize: 13,
    fontWeight: '700',
    color: '#667085',
    marginTop: 10,
    marginBottom: 7,
  },

  titleEditInput: {
    borderWidth: 1,
    borderColor: '#D5DAE1',
    backgroundColor: '#F9FAFB',
    borderRadius: 11,
    padding: 12,
    fontSize: 15,
    fontWeight: '600',
    color: '#172238',
  },

  petitionEditInput: {
    minHeight: 300,
    borderWidth: 1,
    borderColor: '#D5DAE1',
    backgroundColor: '#F9FAFB',
    borderRadius: 11,
    padding: 12,
    fontSize: 14,
    color: '#374151',
    lineHeight: 22,
  },

  saveButton: {
    backgroundColor: '#172238',
    borderRadius: 11,
    paddingVertical: 12,
    alignItems: 'center',
    marginTop: 14,
  },

  saveButtonText: {
    color: '#FFFFFF',
    fontWeight: '700',
    fontSize: 14,
  },

  downloadButtons: {
    flexDirection: 'row',
    gap: 10,
    marginTop: 14,
  },

  fileButton: {
    flex: 1,
    backgroundColor: '#EEF1F5',
    borderWidth: 1,
    borderColor: '#D5DAE1',
    borderRadius: 11,
    paddingVertical: 13,
    alignItems: 'center',
    justifyContent: 'center',
  },

  fileButtonText: {
    color: '#172238',
    fontSize: 14,
    fontWeight: '700',
  },

  petitionSources: {
    marginTop: 22,
    paddingTop: 18,
    borderTopWidth: 1,
    borderTopColor: '#E1E5EA',
  },

  sourcesCard: {
    width: '100%',
    maxWidth: 650,
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 18,
    padding: 20,
    marginTop: 15,
  },

  sourcesTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#172238',
    marginBottom: 12,
  },

  sourceItem: {
    backgroundColor: '#F7F8FA',
    borderRadius: 10,
    padding: 12,
    marginTop: 6,
  },

  sourceName: {
    fontSize: 14,
    fontWeight: '600',
    color: '#374151',
  },

  searchContainer: {
    width: '100%',
    maxWidth: 650,
    flexDirection: 'row',
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 16,
    padding: 7,
    marginTop: 30,
  },

  searchInput: {
    flex: 1,
    paddingHorizontal: 12,
    paddingVertical: 11,
    fontSize: 16,
    color: '#111827',
    outlineWidth: 0,
  } as any,

  searchButton: {
    backgroundColor: '#172238',
    paddingHorizontal: 20,
    justifyContent: 'center',
    alignItems: 'center',
    borderRadius: 11,
    minWidth: 75,
  },

  resultsContainer: {
    width: '100%',
    maxWidth: 650,
    marginTop: 25,
  },

  resultCount: {
    fontSize: 14,
    color: '#7B8496',
    marginBottom: 10,
  },

  lawCard: {
    backgroundColor: '#FFFFFF',
    borderWidth: 1,
    borderColor: '#E1E5EA',
    borderRadius: 16,
    padding: 18,
    marginBottom: 14,
  },

  lawTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: '#172238',
  },

  articleBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#EEF1F5',
    borderRadius: 8,
    paddingHorizontal: 10,
    paddingVertical: 5,
    marginTop: 10,
    marginBottom: 12,
  },

  articleBadgeText: {
    fontSize: 13,
    fontWeight: '700',
    color: '#172238',
  },

  lawContent: {
    fontSize: 14,
    color: '#4B5563',
    lineHeight: 22,
  },

  emptyText: {
    marginTop: 25,
    fontSize: 14,
    color: '#9CA3AF',
    textAlign: 'center',
  },

  errorCard: {
    width: '100%',
    maxWidth: 650,
    backgroundColor: '#FFF5F5',
    borderWidth: 1,
    borderColor: '#FECACA',
    borderRadius: 14,
    padding: 16,
    marginTop: 20,
  },

  errorText: {
    color: '#B42318',
    fontSize: 14,
    textAlign: 'center',
  },

  warning: {
    marginTop: 25,
    fontSize: 12,
    color: '#9CA3AF',
    textAlign: 'center',
  },
});