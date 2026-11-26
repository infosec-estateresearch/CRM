<?php

namespace Espo\Custom\Hooks\Contact;

use Espo\Core\Hook\Hook\AfterSave;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;
use Espo\ORM\Repository\Option\SaveOptions;

/**
 * CRM-IDINT-001R: identity integrity for Contact (AfterSave). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 */
class IdentityAfterSave implements AfterSave
{
    /** Hook order (runs after the platform's own save hooks, so it sees the final values); the platform's default is 9. */
    public static int $order = 99;

    public function __construct(private IdentityGuard $guard)
    {}

    public function afterSave(Entity $entity, SaveOptions $options): void
    {
        $this->guard->afterSave($entity);
    }
}
