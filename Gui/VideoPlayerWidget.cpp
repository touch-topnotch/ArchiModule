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

#include "PreCompiled.h"

#ifndef _PreComp_
#include <QVBoxLayout>
#include <QHBoxLayout>
#include <QStyle>
#include <QUrl>
#include <QFileInfo>
#include <QVideoSink>
#include <QVideoFrame>
#include <QVideoFrameFormat>
#include <QMetaObject>
#include <QMetaEnum>
#include <QMediaMetaData>
#include <QSignalBlocker>
#include <QList>
#include <QVariant>
#endif

#include <algorithm>
#include <cmath>

#include <Base/Console.h>

#include "VideoPlayerWidget.h"

using namespace ArchiGui;

namespace {

QString playbackStateToString(QMediaPlayer::PlaybackState state)
{
    switch (state) {
    case QMediaPlayer::PlayingState:
        return QStringLiteral("Playing");
    case QMediaPlayer::PausedState:
        return QStringLiteral("Paused");
    case QMediaPlayer::StoppedState:
        return QStringLiteral("Stopped");
    }
    return QStringLiteral("Unknown");
}

QString mediaStatusToString(QMediaPlayer::MediaStatus status)
{
    switch (status) {
    case QMediaPlayer::NoMedia:
        return QStringLiteral("NoMedia");
    case QMediaPlayer::LoadingMedia:
        return QStringLiteral("LoadingMedia");
    case QMediaPlayer::LoadedMedia:
        return QStringLiteral("LoadedMedia");
    case QMediaPlayer::StalledMedia:
        return QStringLiteral("StalledMedia");
    case QMediaPlayer::BufferingMedia:
        return QStringLiteral("BufferingMedia");
    case QMediaPlayer::BufferedMedia:
        return QStringLiteral("BufferedMedia");
    case QMediaPlayer::EndOfMedia:
        return QStringLiteral("EndOfMedia");
    case QMediaPlayer::InvalidMedia:
        return QStringLiteral("InvalidMedia");
    }
    return QStringLiteral("Unknown");
}

constexpr bool kEnableVideoPlayerLogging = false;

void logPlayerMessage(const QString& msg)
{
    if (!kEnableVideoPlayerLogging) {
        return;
    }
    
    const QString formatted = QStringLiteral("ArchiGui::VideoPlayerWidget: %1").arg(msg);
    const QByteArray bytes = formatted.toUtf8();
    const char* cstr = bytes.constData();
    
    Base::Console().message("%s\n", cstr);
    Base::Console().log("%s\n", cstr);
    Base::Console().warning("%s\n", cstr);
    Base::Console().error("%s\n", cstr);
}

} // namespace

VideoPlayerWidget::VideoPlayerWidget(QWidget* parent)
    : QWidget(parent)
    , m_player(nullptr)
    , m_videoWidget(nullptr)
    , m_audioOutput(nullptr)
    , m_playPauseButton(nullptr)
    , m_stopButton(nullptr)
    , m_positionSlider(nullptr)
    , m_timeLabel(nullptr)
    , m_isSliderBeingMoved(false)
    , m_loggedFrameCount(0)
    , m_seekPreviewAfterLoad(false)
    , m_controlsVisible(true)
    , m_autoLoop(false)
    , m_frameRate(0.0)
    , m_totalFrames(0)
{
    setupUi();
    
    // Create media player
    m_player = new QMediaPlayer(this);
    m_audioOutput = new QAudioOutput(this);
    m_videoWidget = new QVideoWidget(this);
    m_videoWidget->setAutoFillBackground(false);
    m_videoWidget->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    
    // Connect player to audio and video
    m_player->setAudioOutput(m_audioOutput);
    m_player->setVideoOutput(m_videoWidget);
    if (auto sink = m_videoWidget->videoSink()) {
        logPlayerMessage(QStringLiteral("Video sink detected: %1")
                             .arg(QString::number(reinterpret_cast<quintptr>(sink), 16)));
        connect(sink, &QVideoSink::videoFrameChanged, this, [this](const QVideoFrame& frame) {
            if (!frame.isValid()) {
                logPlayerMessage(QStringLiteral("Received invalid video frame"));
                return;
            }
            if (m_loggedFrameCount < 10) {
                logPlayerMessage(QStringLiteral("Frame #%1: %2x%3 format %4, mapped=%5")
                                     .arg(m_loggedFrameCount + 1)
                                     .arg(frame.width())
                                     .arg(frame.height())
                                     .arg(QVideoFrameFormat::pixelFormatToString(frame.pixelFormat()))
                                     .arg(frame.isMapped() ? QStringLiteral("true")
                                                           : QStringLiteral("false")));
                ++m_loggedFrameCount;
            }
        });
    }
    else {
        logPlayerMessage(QStringLiteral("Video sink not available on QVideoWidget"));
    }
    
    // Add video widget to layout
    QVBoxLayout* mainLayout = qobject_cast<QVBoxLayout*>(layout());
    if (mainLayout) {
        mainLayout->insertWidget(0, m_videoWidget, 1);
    }
    
    // Connect signals
    connect(m_player, &QMediaPlayer::positionChanged, this, &VideoPlayerWidget::onPositionChanged);
    connect(m_player, &QMediaPlayer::durationChanged, this, &VideoPlayerWidget::onDurationChanged);
    connect(m_player, &QMediaPlayer::playbackStateChanged, this, &VideoPlayerWidget::onPlaybackStateChanged);
    connect(m_player, &QMediaPlayer::errorOccurred, this, &VideoPlayerWidget::onMediaError);
    connect(m_player, &QMediaPlayer::mediaStatusChanged, this, &VideoPlayerWidget::onMediaStatusChanged);
    connect(m_player, &QMediaPlayer::hasVideoChanged, this, [](bool available) {
        logPlayerMessage(QStringLiteral("hasVideoChanged: %1").arg(available ? QStringLiteral("true")
                                                                            : QStringLiteral("false")));
    });
    connect(m_player, &QMediaPlayer::videoOutputChanged, this, [this]() {
        QObject* output = m_player->videoOutput();
        QString description = output ? QString::fromLatin1(output->metaObject()->className())
                                     : QStringLiteral("nullptr");
        logPlayerMessage(QStringLiteral("videoOutputChanged: %1").arg(description));
    });
    
    // Set default volume
    m_audioOutput->setVolume(0.7);
    
    logPlayerMessage(QStringLiteral("Video player widget initialized"));
}

VideoPlayerWidget::~VideoPlayerWidget()
{
    if (m_player) {
        m_player->stop();
    }
}

void VideoPlayerWidget::setupUi()
{
    QVBoxLayout* mainLayout = new QVBoxLayout(this);
    mainLayout->setContentsMargins(10, 10, 10, 10);
    mainLayout->setSpacing(10);
    
    // Create controls layout
    QHBoxLayout* controlsLayout = new QHBoxLayout();
    
    // Play/Pause button
    m_playPauseButton = new QPushButton(this);
    m_playPauseButton->setIcon(style()->standardIcon(QStyle::SP_MediaPlay));
    m_playPauseButton->setToolTip(tr("Play"));
    connect(m_playPauseButton, &QPushButton::clicked, this, &VideoPlayerWidget::onPlayPauseClicked);
    controlsLayout->addWidget(m_playPauseButton);
    
    // Stop button
    m_stopButton = new QPushButton(this);
    m_stopButton->setIcon(style()->standardIcon(QStyle::SP_MediaStop));
    m_stopButton->setToolTip(tr("Stop"));
    connect(m_stopButton, &QPushButton::clicked, this, &VideoPlayerWidget::onStopClicked);
    controlsLayout->addWidget(m_stopButton);
    
    // Time label
    m_timeLabel = new QLabel(QStringLiteral("00:00 / 00:00"), this);
    m_timeLabel->setMinimumWidth(100);
    controlsLayout->addWidget(m_timeLabel);
    
    // Position slider
    m_positionSlider = new QSlider(Qt::Horizontal, this);
    m_positionSlider->setRange(0, 0);
    connect(m_positionSlider, &QSlider::sliderMoved, this, &VideoPlayerWidget::onSliderMoved);
    connect(m_positionSlider, &QSlider::sliderPressed, this, [this]() {
        m_isSliderBeingMoved = true;
        if (m_player) {
            m_player->setPosition(frameIndexToPosition(m_positionSlider->value()));
        }
    });
    connect(m_positionSlider, &QSlider::sliderReleased, this, [this]() {
        m_isSliderBeingMoved = false;
        if (m_player) {
            m_player->setPosition(frameIndexToPosition(m_positionSlider->value()));
        }
    });
    controlsLayout->addWidget(m_positionSlider, 1);
    
    mainLayout->addLayout(controlsLayout);
    setLayout(mainLayout);
}

void VideoPlayerWidget::loadVideo(const QString& videoPath)
{
    if (!m_player) {
        Q_EMIT errorOccurred(tr("Player not initialized"));
        return;
    }

    QFileInfo info(videoPath);
    logPlayerMessage(QStringLiteral("Loading video: %1 (exists=%2, size=%3 bytes)")
                         .arg(videoPath,
                              info.exists() ? QStringLiteral("true") : QStringLiteral("false"),
                              info.exists() ? QString::number(info.size())
                                            : QStringLiteral("n/a")));
    
    m_player->setSource(QUrl::fromLocalFile(videoPath));
    m_player->setPosition(0);  // Reset to start
    m_seekPreviewAfterLoad = true;
    m_frameRate = 0.0;
    m_totalFrames = 0;
}

void VideoPlayerWidget::play()
{
    if (m_player) {
        logPlayerMessage(QStringLiteral("Play requested"));
        m_player->play();
    }
}

void VideoPlayerWidget::pause()
{
    if (m_player) {
        logPlayerMessage(QStringLiteral("Pause requested"));
        m_player->pause();
    }
}

void VideoPlayerWidget::stop()
{
    if (m_player) {
        logPlayerMessage(QStringLiteral("Stop requested"));
        m_player->stop();
        showInitialPreviewFrame();
    }
}

void VideoPlayerWidget::setPosition(qint64 position)
{
    if (m_player) {
        m_player->setPosition(position);
    }
}

void VideoPlayerWidget::setVolume(int volume)
{
    if (!m_audioOutput) {
        return;
    }
    int clamped = volume;
    if (clamped < 0) {
        clamped = 0;
    }
    if (clamped > 100) {
        clamped = 100;
    }
    m_audioOutput->setVolume(clamped / 100.0);
}

bool VideoPlayerWidget::isPlaying() const
{
    return m_player && m_player->playbackState() == QMediaPlayer::PlayingState;
}

qint64 VideoPlayerWidget::position() const
{
    return m_player ? m_player->position() : 0;
}

qint64 VideoPlayerWidget::duration() const
{
    return m_player ? m_player->duration() : 0;
}

int VideoPlayerWidget::volume() const
{
    if (!m_audioOutput) {
        return 0;
    }
    return static_cast<int>(m_audioOutput->volume() * 100.0);
}

void VideoPlayerWidget::setControlsVisible(bool visible)
{
    m_controlsVisible = visible;
    const QList<QWidget*> controls = {m_playPauseButton, m_stopButton, m_positionSlider, m_timeLabel};
    for (QWidget* control : controls) {
        if (control) {
            control->setVisible(visible);
        }
    }
    if (layout()) {
        layout()->invalidate();
        layout()->activate();
    }
}

bool VideoPlayerWidget::controlsVisible() const
{
    return m_controlsVisible;
}

void VideoPlayerWidget::setAutoLoop(bool loop)
{
    m_autoLoop = loop;
#if QT_VERSION >= QT_VERSION_CHECK(6, 4, 0)
    if (m_player) {
        m_player->setLoops(loop ? QMediaPlayer::Infinite : 1);
    }
#endif
}

bool VideoPlayerWidget::autoLoop() const
{
    return m_autoLoop;
}

void VideoPlayerWidget::onPlayPauseClicked()
{
    if (!m_player) return;
    
    if (m_player->playbackState() == QMediaPlayer::PlayingState) {
        pause();
    } else {
        play();
    }
}

void VideoPlayerWidget::onStopClicked()
{
    stop();
}

void VideoPlayerWidget::onPositionChanged(qint64 position)
{
    if (!m_isSliderBeingMoved && m_positionSlider) {
        int frameIndex = positionToFrameIndex(position);
        QSignalBlocker blocker(m_positionSlider);
        m_positionSlider->setValue(frameIndex);
    }
    
    if (m_timeLabel && m_player) {
        QString currentTime = formatTime(position);
        QString totalTime = formatTime(m_player->duration());
        m_timeLabel->setText(QStringLiteral("%1 / %2").arg(currentTime, totalTime));
    }
    
    Q_EMIT positionChanged(position);
}

void VideoPlayerWidget::onDurationChanged(qint64 duration)
{
    updateFrameMapping(duration);
    if (m_positionSlider) {
        m_positionSlider->setRange(0, std::max(0, m_totalFrames - 1));
        m_positionSlider->setSingleStep(1);
    }

    Q_EMIT durationChanged(duration);
}

void VideoPlayerWidget::onSliderMoved(int position)
{
    qint64 targetPosition = frameIndexToPosition(position);
    if (m_timeLabel && m_player) {
        QString currentTime = formatTime(targetPosition);
        QString totalTime = formatTime(m_player->duration());
        m_timeLabel->setText(QStringLiteral("%1 / %2").arg(currentTime, totalTime));
    }

    if (m_isSliderBeingMoved && m_player) {
        m_player->setPosition(targetPosition);
    }
}

void VideoPlayerWidget::onPlaybackStateChanged(QMediaPlayer::PlaybackState state)
{
    if (!m_playPauseButton) return;

    logPlayerMessage(QStringLiteral("Playback state changed: %1").arg(playbackStateToString(state)));
    
    switch (state) {
    case QMediaPlayer::PlayingState:
        m_playPauseButton->setIcon(style()->standardIcon(QStyle::SP_MediaPause));
        m_playPauseButton->setToolTip(tr("Pause"));
        Q_EMIT playbackStateChanged(true);
        break;
    case QMediaPlayer::PausedState:
    case QMediaPlayer::StoppedState:
        m_playPauseButton->setIcon(style()->standardIcon(QStyle::SP_MediaPlay));
        m_playPauseButton->setToolTip(tr("Play"));
        Q_EMIT playbackStateChanged(false);
        break;
    }
}

void VideoPlayerWidget::onMediaError(QMediaPlayer::Error error, const QString& errorString)
{
    Q_UNUSED(error);
    logPlayerMessage(QStringLiteral("Media error: %1").arg(errorString));
    Q_EMIT errorOccurred(errorString);
}

void VideoPlayerWidget::onMediaStatusChanged(QMediaPlayer::MediaStatus status)
{
    logPlayerMessage(QStringLiteral("Media status changed: %1").arg(mediaStatusToString(status)));

    if (status == QMediaPlayer::LoadedMedia) {
        if (m_seekPreviewAfterLoad) {
            showInitialPreviewFrame();
            m_seekPreviewAfterLoad = false;
        }
        if (m_player && m_player->playbackState() != QMediaPlayer::PlayingState) {
            m_player->play();
            m_player->pause();
        }
    }
    else if (status == QMediaPlayer::EndOfMedia) {
        if (m_autoLoop) {
            if (m_player) {
                const bool wasPlaying = m_player->playbackState() == QMediaPlayer::PlayingState;
                m_player->setPosition(0);
                if (wasPlaying) {
                    m_player->play();
                }
            }
        }
        else {
            showEndPreviewFrame();
        }
    }
}

QString VideoPlayerWidget::formatTime(qint64 ms) const
{
    int seconds = static_cast<int>(ms / 1000);
    int minutes = seconds / 60;
    seconds %= 60;
    
    return QStringLiteral("%1:%2")
        .arg(minutes, 2, 10, QLatin1Char('0'))
        .arg(seconds, 2, 10, QLatin1Char('0'));
}

void VideoPlayerWidget::showInitialPreviewFrame()
{
    if (!m_player) {
        return;
    }
    const qint64 pos = previewFramePosition();
    m_player->setPosition(pos);
}

void VideoPlayerWidget::showEndPreviewFrame()
{
    if (!m_player) {
        return;
    }
    const qint64 pos = endFramePosition();
    m_player->setPosition(pos);
}

qint64 VideoPlayerWidget::previewFramePosition() const
{
    constexpr qint64 previewOffsetMs = 120;
    if (m_frameRate > 0 && m_totalFrames > 0) {
        int frameIndex = static_cast<int>(std::llround((previewOffsetMs / 1000.0) * m_frameRate));
        frameIndex = std::clamp(frameIndex, 0, std::max(0, m_totalFrames - 1));
        return frameIndexToPosition(frameIndex);
    }
    if (!m_player) {
        return previewOffsetMs;
    }
    const qint64 duration = m_player->duration();
    if (duration <= 0) {
        return previewOffsetMs;
    }
    if (duration <= previewOffsetMs) {
        return std::max<qint64>(0, duration / 4);
    }
    return previewOffsetMs;
}

qint64 VideoPlayerWidget::endFramePosition() const
{
    constexpr qint64 endOffsetMs = 200;
    if (m_frameRate > 0 && m_totalFrames > 0) {
        int frameIndex = std::max(0, m_totalFrames - 1);
        qint64 pos = frameIndexToPosition(frameIndex);
        return pos > endOffsetMs ? pos - endOffsetMs : pos;
    }
    if (!m_player) {
        return 0;
    }
    const qint64 duration = m_player->duration();
    if (duration <= 0) {
        return 0;
    }
    if (duration <= endOffsetMs) {
        return std::max<qint64>(0, duration - 1);
    }
    return duration - endOffsetMs;
}

qint64 VideoPlayerWidget::frameIndexToPosition(int frameIndex) const
{
    if (m_frameRate <= 0) {
        return static_cast<qint64>(frameIndex);
    }
    double positionMs = (static_cast<double>(frameIndex) / m_frameRate) * 1000.0;
    return static_cast<qint64>(std::llround(positionMs));
}

int VideoPlayerWidget::positionToFrameIndex(qint64 position) const
{
    if (m_frameRate <= 0) {
        return static_cast<int>(position);
    }
    double frame = (static_cast<double>(position) * m_frameRate) / 1000.0;
    int idx = static_cast<int>(std::llround(frame));
    return std::clamp(idx, 0, std::max(0, m_totalFrames - 1));
}

void VideoPlayerWidget::updateFrameMapping(qint64 duration)
{
    double rate = 0.0;
    if (m_player) {
        QVariant value = m_player->metaData().value(QMediaMetaData::VideoFrameRate);
        if (value.isValid()) {
            rate = value.toDouble();
        }
    }
    if (rate <= 0.0) {
        rate = 30.0;
    }
    m_frameRate = rate;

    if (duration > 0) {
        double framesExact = (static_cast<double>(duration) * rate) / 1000.0;
        m_totalFrames = std::max(1, static_cast<int>(std::llround(framesExact)));
    }
    else {
        m_totalFrames = 0;
    }
}
