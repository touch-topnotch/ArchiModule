/***************************************************************************
 *   Copyright (c) 2025 Dmitry Tetkin                                     *
 *                                                                         *
 *   This file is part of the FreeCAD CAx development system.              *
 *                                                                         *
 *   This library is free software; you can redistribute it and/or         *
 *   modify it under the terms of the GNU Library General Public           *
 *   License as published by the Free Software Foundation; either          *
 *   version 2 of the License, or (at your option) any later version.      *
 *                                                                         *
 *   This library  is distributed in the hope that it will be useful,      *
 *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
 *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
 *   GNU Library General Public License for more details.                  *
 *                                                                         *
 *   You should have received a copy of the GNU Library General Public     *
 *   License along with this library; see the file COPYING.LIB. If not,    *
 *   write to the Free Software Foundation, Inc., 59 Temple Place,         *
 *   Suite 330, Boston, MA  02111-1307, USA                                *
 *                                                                         *
 ***************************************************************************/

#ifndef ARCHIGUI_VIDEOPLAYERWIDGET_H
#define ARCHIGUI_VIDEOPLAYERWIDGET_H

#include <QWidget>
#include <QMediaPlayer>
#include <QVideoWidget>
#include <QAudioOutput>
#include <QPushButton>
#include <QSlider>
#include <QLabel>
#include <QString>

namespace ArchiGui {

class VideoPlayerWidget : public QWidget
{
    Q_OBJECT

public:
    explicit VideoPlayerWidget(QWidget* parent = nullptr);
    ~VideoPlayerWidget() override;

    // Load video from file path
    void loadVideo(const QString& videoPath);
    
    // Playback control
    void play();
    void pause();
    void stop();
    void setPosition(qint64 position);
    void setVolume(int volume);
    void setControlsVisible(bool visible);
    bool controlsVisible() const;
    void setAutoLoop(bool loop);
    bool autoLoop() const;
    
    // Get current state
    bool isPlaying() const;
    qint64 position() const;
    qint64 duration() const;
    int volume() const;

Q_SIGNALS:
    void playbackStateChanged(bool playing);
    void positionChanged(qint64 position);
    void durationChanged(qint64 duration);
    void errorOccurred(const QString& error);

private Q_SLOTS:
    void onPlayPauseClicked();
    void onStopClicked();
    void onPositionChanged(qint64 position);
    void onDurationChanged(qint64 duration);
    void onSliderMoved(int position);
    void onPlaybackStateChanged(QMediaPlayer::PlaybackState state);
    void onMediaError(QMediaPlayer::Error error, const QString& errorString);
    void onMediaStatusChanged(QMediaPlayer::MediaStatus status);

private:
    void setupUi();
    QString formatTime(qint64 ms) const;
    qint64 frameIndexToPosition(int frameIndex) const;
    int positionToFrameIndex(qint64 position) const;
    void updateFrameMapping(qint64 duration);
    void showInitialPreviewFrame();
    void showEndPreviewFrame();
    qint64 previewFramePosition() const;
    qint64 endFramePosition() const;

    QMediaPlayer* m_player;
    QVideoWidget* m_videoWidget;
    QAudioOutput* m_audioOutput;
    
    QPushButton* m_playPauseButton;
    QPushButton* m_stopButton;
    QSlider* m_positionSlider;
    QLabel* m_timeLabel;
    
    bool m_isSliderBeingMoved;
    int m_loggedFrameCount;
    bool m_seekPreviewAfterLoad;
    bool m_controlsVisible;
    bool m_autoLoop;
    double m_frameRate;
    int m_totalFrames;
};

} // namespace ArchiGui

#endif // ARCHIGUI_VIDEOPLAYERWIDGET_H
