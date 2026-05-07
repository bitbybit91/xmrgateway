<?php

declare(strict_types=1);

namespace App\Services;

use PHPMailer\PHPMailer\PHPMailer;
use PHPMailer\PHPMailer\SMTP;
use PHPMailer\PHPMailer\Exception;

class Mailer
{
    private function createMailer(): PHPMailer
    {
        $mail = new PHPMailer(true);
        $mail->isSMTP();
        $mail->Host       = MAIL_HOST;
        $mail->Port       = MAIL_PORT;
        $mail->SMTPAuth   = MAIL_USERNAME !== '';
        $mail->Username   = MAIL_USERNAME;
        $mail->Password   = MAIL_PASSWORD;
        $mail->SMTPSecure = MAIL_ENCRYPTION === 'ssl' ? PHPMailer::ENCRYPTION_SMTPS : PHPMailer::ENCRYPTION_STARTTLS;
        $mail->setFrom(MAIL_FROM_ADDRESS, MAIL_FROM_NAME);
        $mail->isHTML(true);
        $mail->CharSet = 'UTF-8';
        return $mail;
    }

    public function sendWelcome(string $to, string $name, string $verificationToken): bool
    {
        $verifyUrl = APP_URL . '/verify-email?token=' . urlencode($verificationToken);
        $subject   = 'Welcome to ' . APP_NAME . ' — Verify your email';
        $body      = $this->wrap("
            <h2>Welcome, {$name}!</h2>
            <p>Thank you for joining " . APP_NAME . ". Please verify your email address to activate your account.</p>
            <p><a href=\"{$verifyUrl}\" style=\"background:#C9A227;color:#000;padding:12px 24px;text-decoration:none;border-radius:4px;\">Verify Email</a></p>
            <p>Or copy this link:<br><small>{$verifyUrl}</small></p>
        ");
        return $this->send($to, $name, $subject, $body);
    }

    public function sendEmailVerification(string $to, string $name, string $token): bool
    {
        return $this->sendWelcome($to, $name, $token);
    }

    public function sendInvestmentConfirmed(string $to, string $name, array $investment, array $plan): bool
    {
        $subject = 'Investment Confirmed — ' . APP_NAME;
        $amount  = '$' . number_format($investment['amount_usd'], 2);
        $endDate = date('F j, Y', strtotime($investment['end_date'] ?? '+30 days'));
        $body    = $this->wrap("
            <h2>Your investment is active!</h2>
            <p>Hi {$name}, your investment of <strong>{$amount}</strong> in the <strong>{$plan['name']}</strong> plan has been confirmed and is now earning returns.</p>
            <table style=\"border-collapse:collapse;width:100%\">
              <tr><td style=\"padding:8px;border:1px solid #ddd\">Plan</td><td style=\"padding:8px;border:1px solid #ddd\">{$plan['name']}</td></tr>
              <tr><td style=\"padding:8px;border:1px solid #ddd\">Amount</td><td style=\"padding:8px;border:1px solid #ddd\">{$amount}</td></tr>
              <tr><td style=\"padding:8px;border:1px solid #ddd\">Daily ROI</td><td style=\"padding:8px;border:1px solid #ddd\">{$plan['daily_roi_percent']}%</td></tr>
              <tr><td style=\"padding:8px;border:1px solid #ddd\">Maturity Date</td><td style=\"padding:8px;border:1px solid #ddd\">{$endDate}</td></tr>
            </table>
            <p><a href=\"" . APP_URL . "/dashboard\">View Dashboard</a></p>
        ");
        return $this->send($to, $name, $subject, $body);
    }

    public function sendRoiAccrual(string $to, string $name, float $roiUsd): bool
    {
        $subject  = 'Daily ROI Update — ' . APP_NAME;
        $formatted = '$' . number_format($roiUsd, 4);
        $body     = $this->wrap("
            <h2>Your daily returns</h2>
            <p>Hi {$name}, you earned <strong>{$formatted}</strong> today from your active investments.</p>
            <p><a href=\"" . APP_URL . "/dashboard\">View your dashboard</a></p>
        ");
        return $this->send($to, $name, $subject, $body);
    }

    public function sendWithdrawalApproved(string $to, string $name, float $amount): bool
    {
        $formatted = '$' . number_format($amount, 2);
        $body = $this->wrap("
            <h2>Withdrawal Approved</h2>
            <p>Hi {$name}, your withdrawal of <strong>{$formatted}</strong> has been approved and is being processed.</p>
        ");
        return $this->send($to, $name, 'Withdrawal Approved — ' . APP_NAME, $body);
    }

    public function sendWithdrawalRejected(string $to, string $name, float $amount, string $reason): bool
    {
        $formatted = '$' . number_format($amount, 2);
        $body = $this->wrap("
            <h2>Withdrawal Rejected</h2>
            <p>Hi {$name}, your withdrawal request of <strong>{$formatted}</strong> was rejected.</p>
            <p><strong>Reason:</strong> " . htmlspecialchars($reason) . "</p>
            <p>Please contact support if you have questions.</p>
        ");
        return $this->send($to, $name, 'Withdrawal Update — ' . APP_NAME, $body);
    }

    public function sendPasswordReset(string $to, string $name, string $token): bool
    {
        $resetUrl = APP_URL . '/reset-password?token=' . urlencode($token);
        $body     = $this->wrap("
            <h2>Password Reset Request</h2>
            <p>Hi {$name}, click the button below to reset your password. This link expires in 1 hour.</p>
            <p><a href=\"{$resetUrl}\" style=\"background:#C9A227;color:#000;padding:12px 24px;text-decoration:none;border-radius:4px;\">Reset Password</a></p>
            <p>If you did not request this, ignore this email.</p>
        ");
        return $this->send($to, $name, 'Password Reset — ' . APP_NAME, $body);
    }

    private function send(string $to, string $name, string $subject, string $htmlBody): bool
    {
        try {
            $mail = $this->createMailer();
            $mail->addAddress($to, $name);
            $mail->Subject = $subject;
            $mail->Body    = $htmlBody;
            $mail->AltBody = strip_tags($htmlBody);
            $mail->send();
            return true;
        } catch (Exception $e) {
            error_log('[Mailer] Failed to send to ' . $to . ': ' . $e->getMessage());
            return false;
        }
    }

    private function wrap(string $content): string
    {
        $appName = APP_NAME;
        $appUrl  = APP_URL;
        return <<<HTML
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8"><style>
          body{font-family:Arial,sans-serif;background:#f5f5f5;margin:0;padding:0}
          .container{max-width:600px;margin:40px auto;background:#fff;border-radius:8px;overflow:hidden}
          .header{background:#0a0a0a;padding:24px 32px;color:#C9A227;font-size:22px;font-weight:bold}
          .body{padding:32px;color:#333;line-height:1.6}
          .footer{background:#f5f5f5;padding:16px 32px;color:#888;font-size:12px;text-align:center}
          a{color:#C9A227}
        </style></head>
        <body>
          <div class="container">
            <div class="header">{$appName}</div>
            <div class="body">{$content}</div>
            <div class="footer">&copy; {$appName} · <a href="{$appUrl}">{$appUrl}</a></div>
          </div>
        </body></html>
        HTML;
    }
}
