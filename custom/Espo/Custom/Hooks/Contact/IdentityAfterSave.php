<?php

namespace Espo\Custom\Hooks\Contact;

use Espo\Core\Hook\Hook\AfterSave;
use Espo\Custom\Classes\Identity\IdentityGuard;
use Espo\ORM\Entity;

/**
 * CRM-IDINT-001: identity integrity for Contact (AfterSave). All rules live in
 * Espo\Custom\Classes\Identity\IdentityGuard; this hook only hands over. It has
 * no administrator or service-account exemption.
 *
 * @implements AfterSave<Entity>
 */
class IdentityAfterSave implements AfterSave
{
    public function __construct(private IdentityGuard $guard)
    {}

    public function afterSave(Entity $entity, mixed ...$rest): void
    {
        $this->guard->afterSave($entity);
    }
}
