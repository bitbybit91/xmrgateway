<?php

declare(strict_types=1);

namespace App\Controllers;

use App\Core\{View, Session, Csrf, Validator, Database};
use App\Models\User;
use App\Services\Mailer;

class AuthController
{
    public function loginForm(array $params = []): void
    {
        if (Session::isLoggedIn()) {
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }
        (new View())->display('auth/login.twig');
    }

    public function login(array $params = []): void
    {
        Csrf::middleware();

        $email    = trim($_POST['email']    ?? '');
        $password = $_POST['password']      ?? '';
        $ip       = $_SERVER['REMOTE_ADDR'] ?? '127.0.0.1';

        // Rate limiting: max 5 attempts per 15 minutes per IP
        $db      = Database::getInstance();
        $window  = date('Y-m-d H:i:s', strtotime('-15 minutes'));
        $attempts = (int)($db->fetchOne(
            "SELECT COUNT(*) as cnt FROM audit_logs WHERE action = 'login_failed' AND ip_address = ? AND created_at > ?",
            [$ip, $window]
        )['cnt'] ?? 0);

        if ($attempts >= 5) {
            Session::flash('error', 'Too many login attempts. Please wait 15 minutes.');
            header('Location: ' . APP_URL . '/login'); exit;
        }

        $user = User::findByEmail($email);

        if (!$user || !password_verify($password, $user['password_hash'])) {
            $db->insert('audit_logs', [
                'action'     => 'login_failed',
                'ip_address' => $ip,
                'new_values' => json_encode(['email' => $email]),
                'created_at' => date('Y-m-d H:i:s'),
            ]);
            Session::flash('error', 'Invalid email or password.');
            header('Location: ' . APP_URL . '/login'); exit;
        }

        if ($user['status'] === 'pending') {
            Session::flash('error', 'Please verify your email before logging in.');
            header('Location: ' . APP_URL . '/login'); exit;
        }

        if (in_array($user['status'], ['suspended', 'banned'], true)) {
            Session::flash('error', 'Your account has been suspended.');
            header('Location: ' . APP_URL . '/login'); exit;
        }

        Session::login($user);

        $db->insert('audit_logs', [
            'user_id'    => $user['id'],
            'action'     => 'login_success',
            'ip_address' => $ip,
            'created_at' => date('Y-m-d H:i:s'),
        ]);

        header('Location: ' . APP_URL . ($user['role'] === 'admin' ? '/admin' : '/dashboard'));
        exit;
    }

    public function registerForm(array $params = []): void
    {
        if (Session::isLoggedIn()) {
            header('Location: ' . APP_URL . '/dashboard'); exit;
        }
        (new View())->display('auth/register.twig');
    }

    public function register(array $params = []): void
    {
        Csrf::middleware();

        $v = (new Validator())->validate($_POST, [
            'name'                  => 'required|min:2|max:120',
            'email'                 => 'required|email|unique:users,email',
            'password'              => 'required|min:8|max:128',
            'password_confirmation' => 'required|confirmed',
        ]);

        if (!$v['valid']) {
            Session::flash('error', implode(' ', $v['errors']));
            header('Location: ' . APP_URL . '/register'); exit;
        }

        $token  = bin2hex(random_bytes(32));
        $userId = User::create([
            'name'                     => htmlspecialchars(trim($_POST['name'])),
            'email'                    => strtolower(trim($_POST['email'])),
            'password'                 => $_POST['password'],
            'status'                   => 'pending',
            'email_verification_token' => $token,
        ]);

        (new Mailer())->sendWelcome(strtolower(trim($_POST['email'])), trim($_POST['name']), $token);

        Session::flash('success', 'Account created! Please check your email to verify your account.');
        header('Location: ' . APP_URL . '/login'); exit;
    }

    public function verifyEmail(array $params = []): void
    {
        $token = trim($_GET['token'] ?? '');
        if ($token && User::verifyEmail($token)) {
            Session::flash('success', 'Email verified! You can now log in.');
        } else {
            Session::flash('error', 'Invalid or expired verification token.');
        }
        header('Location: ' . APP_URL . '/login'); exit;
    }

    public function logout(array $params = []): void
    {
        Session::logout();
        header('Location: ' . APP_URL . '/'); exit;
    }

    public function forgotPasswordForm(array $params = []): void
    {
        (new View())->display('auth/forgot_password.twig');
    }

    public function forgotPassword(array $params = []): void
    {
        Csrf::middleware();
        $email = strtolower(trim($_POST['email'] ?? ''));
        $user  = User::findByEmail($email);

        // Always show the same message to avoid email enumeration
        Session::flash('success', 'If that email exists, a reset link has been sent.');

        if ($user) {
            $token = User::generatePasswordReset($user['id']);
            (new Mailer())->sendPasswordReset($email, $user['name'], $token);
        }

        header('Location: ' . APP_URL . '/forgot-password'); exit;
    }

    public function resetPasswordForm(array $params = []): void
    {
        $token = $_GET['token'] ?? '';
        (new View())->display('auth/reset_password.twig', compact('token'));
    }

    public function resetPassword(array $params = []): void
    {
        Csrf::middleware();
        $token    = $_POST['token']    ?? '';
        $password = $_POST['password'] ?? '';
        $confirm  = $_POST['password_confirmation'] ?? '';

        if ($password !== $confirm || strlen($password) < 8) {
            Session::flash('error', 'Passwords do not match or are too short (min 8 chars).');
            header('Location: ' . APP_URL . '/reset-password?token=' . urlencode($token)); exit;
        }

        $db   = Database::getInstance();
        $user = $db->fetchOne(
            "SELECT * FROM users WHERE password_reset_token = ? AND password_reset_expires > NOW()",
            [$token]
        );

        if (!$user) {
            Session::flash('error', 'Invalid or expired reset token.');
            header('Location: ' . APP_URL . '/forgot-password'); exit;
        }

        User::updatePassword($user['id'], $password);
        Session::flash('success', 'Password reset successfully. Please log in.');
        header('Location: ' . APP_URL . '/login'); exit;
    }
}
